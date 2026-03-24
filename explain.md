# Drishti - System Explanation Guide

This document is designed to help you confidently present the "Drishti" project. It breaks down the system's architecture, from the moment a video frame is captured to the moment an alert appears on the screen.

---

## 1. System Overview

**Drishti** is a real-time crowd monitoring system built to analyze video feeds, track individuals, and intelligently assess the risk of overcrowding or panic. 

**The Complete Pipeline:**
1. **Video Input:** The system receives video from a CCTV camera, a live webcam, or a pre-recorded file.
2. **Frame Processing:** The video is broken down into individual images (frames). To optimize performance, the system processes a subset of these frames (e.g., every 5th frame depending on the frame rate).
3. **Detection (YOLO):** Each processed frame is passed into a YOLO (You Only Look Once) model, which draws bounding boxes around all people in the frame.
4. **Tracking (ByteTrack):** The detections are handed to ByteTrack, which assigns a unique ID to each person and matches them across consecutive frames so we know who is who.
5. **Frame Metrics Calculation:** The system calculates the speed of each person, the crowd density, and social distance violations.
6. **Aggregation:** Frame-by-frame data is extremely noisy, so the backend aggregates the data into **5-second time windows**.
7. **Risk Engine:** The aggregated data is fed into a Context-Aware Risk Engine, which considers the environment type (e.g., transit rush vs. static waiting area) to compute a final risk score (Normal, Busy, Warning, Critical).
8. **Frontend/UI:** The final aggregated risk levels, heatmaps, and AI-generated text alerts are mapped directly to the UI for operators to act upon.

---

## 2. Detection (YOLO)

The first step in understanding the crowd is simply "seeing" the people.

* **Model Used:** We use **YOLOv8** (specifically lightweight versions like `nano.pt` or `yolov8m.pt` for CPU/speed efficiency).
* **What it Outputs:** For every single frame, YOLO outputs a list of objects. We filter this to only look at **Class ID 0** (Person). For each person, it gives:
  * **Bounding Box:** Coordinates `[x1, y1, x2, y2]` specifying where the person is.
  * **Confidence Score:** A percentage (e.g., 0.85) representing how sure the model is that the object is a human.
* **Threshold Filtering:** We use a `MIN_CONF` threshold of `0.15` (15%). If YOLO is less than 15% confident, the prediction is discarded. This prevents false positives like chairs or shadows being counted as people.
* **Detection Count:** The crowd count for a single frame is simply the total number of bounding boxes that pass the confidence threshold.

---

## 3. Tracking (ByteTrack)

Detection tells us *where* people are, but **Tracking** tells us *where they are going*. 

* **The Problem It Solves:** If two people cross paths, or someone walks behind a pillar, a basic detector loses them. ByteTrack solves the "Identity Association" problem, ensuring Person ID 5 remains Person ID 5.
* **Difference from Detection:** Detection acts on a single still image. Tracking takes historical data (past frames) and links current detections to past trajectories.
* **How IDs are assigned & Matched:**
  * Objects are matched between the previous frame and the current frame primarily using **IoU (Intersection over Union)**, which measures how much the new bounding box overlaps with the predicted location of the old bounding box.
* **High vs Low Confidence:** ByteTrack is unique because it doesn't just throw away low-confidence detections. It matches high-confidence detections first. If a tracked person is missing, it then looks at the *low-confidence* detections (perhaps the person is partially occluded/hidden) to sustain the track.
* **Lost Tracks:** If a person completely disappears (leaves the frame), they are kept in a "Lost Track Buffer" for a maximum age of `3 seconds`. If they reappear within 3 seconds, they get their old ID back. If not, the track expires and their movement data is finalized.

---

## 4. Metrics & Calculations (CRITICAL)

Once we have tracked individuals, we calculate their movement.

### A. Crowd Count
* **Calculation:** The exact `len(humans_detected)` in a specific frame.
* *Example:* If YOLO outputs 12 verified bounding boxes -> Crowd Count = 12.

### B. Speed & Movement (Per Person)
* **Calculation:** Speed is determined by calculating the **Euclidean Distance** between a person's center coordinate `(cx, cy)` in the current frame and their position in the previous tracked frame, divided by the time passed.
* **Formula:** `Speed = euclidean(current_pos, previous_pos) / TIME_STEP`
* *Variables:*
  * `current_pos[x,y]`: e.g., (100, 200)
  * `previous_pos[x,y]`: e.g., (100, 210)
  * `TIME_STEP`: The time duration between the processed frames.
* *Example:* Distance moved = 10 pixels. Time step = 0.16 seconds. Speed = 10 / 0.16 = 62.5 pixels/sec.
* **Fast Motion Ratio:** If a person's speed exceeds `SPEED_THRESHOLD` (10.0 pixels per timestep), they are flagged as moving fast. The average is `fast_motion_count / total_people`.

### C. Density Score
* **Calculation:** We calculate the area of the camera frame covered by humans.
* **Formula:** `Density = Avg_Normalized_BBox_Area * Human_Count`
* *Variables:* 
  * `Normalized_BBox_Area`: `(width * height of person box) / (total frame area)`.
* *Example:* If a person takes up 5% of the screen (0.05), and there are 20 people, the raw density score is `0.05 * 20 = 1.0`.

### D. Crowd Growth Rate (Surge)
* **Calculation:** Checks how rapidly the crowd is increasing between aggregated time windows.
* **Formula:** `(Current_Avg_Count - Previous_Avg_Count) / Previous_Avg_Count`
* *Example:* Previous 5 seconds had 50 people. Current 5 seconds has 60. Surge = `(60 - 50) / 50 = +0.20` (20% growth).

---

## 5. Risk Engine (`risk_engine.py`)

The Risk Engine is a sophisticated, **Weighted-Based System** (not just simple hardcoded rules). It dynamically calculates risk based on environmental context (e.g., A library has different rules than a train station).

* **Inputs Used:** It uses three main metrics: Density, Motion Speed, and Surge (Crowd Growth Rate).
* **The Logic/Calculations:**
  1. **Density Score:** `Avg Human Count / Capacity of Area` (clamped 0 - 1.5).
  2. **Motion Score:** `Avg Motion Speed / Expected Speed` (Expected speed varies if flow type is "STATIC" vs "TRANSIT_RUSH").
  3. **Surge Score:** `abs(Crowd Growth Rate) / Capacity`.
* **Final Risk Computation:**
  ```text
  Raw Risk = (Weight_1 * Adjusted_Density) + (Weight_2 * Motion_Score) + (Weight_3 * Surge_Score)
  Final Risk Score = (Raw Risk * Sensitivity Multiplier)
  ```
  The weights automatically change based on the system "Goal". For example, if Goal is `STAY`, density is weighted 50% and motion 20%. If Goal is `SECURITY`, unexpected motion is weighted 60%.
* **Thresholds & Alerts:**
  * `<= 0.30` -> **NORMAL**
  * `<= 0.55` -> **BUSY**
  * `<= 0.75` -> **WARNING** (Triggers UI snapshot)
  * `> 0.75` ->  **CRITICAL** (Triggers automated webhook alert via n8n)

---

## 6. Aggregation Logic (`aggregator.py`)

Because real-time computer vision skips frames or has minor detection flickers, the raw data is very noisy. 

* **How Data is Combined:** The system uses a **Tumbling Time Window of 5 seconds**. 
* **Averaging:** It collects all frames processed within those 5 seconds. It calculates the `avg_human_count`, `max_human_count`, and `avg_motion_speed` of that exact 5-second block.
* **Why it's needed:** If a person is temporarily blocked by a pillar for 10 frames, the frame-level crowd count drops from 50 to 49, triggering false dips. Aggregating over 5 seconds smooths out these tiny drops and provides the Risk Engine with a stable statistical baseline.

### Aggregated Output Variables (The Final Payload)
When an aggregation window finishes, it generates a final block of data for the UI and AI. Here is what each value means using a real example:

* **`motion_score` (e.g., 0.0783):** The ratio of the crowd's actual speed versus the expected speed for this environment type. A score of `1.0` means they are walking exactly as fast as expected. `0.0783` means the crowd is moving very slowly (about 7.8% of the expected maximum speed).
* **`surge_score` (e.g., 0.0012):** Measures how violently the crowd size is changing. It is the crowd growth rate divided by the maximum capacity. `0.0012` is extremely low, meaning the crowd size is very stable right now.
* **`risk_score` (e.g., 0.3666):** The final mathematical combination of Density, Motion, and Surge. It ranges from `0.0` (completely empty/safe) to `1.0` (maximum danger). A score of `0.3666` puts it slightly above the "Normal" threshold.
* **`risk_level` (e.g., "BUSY"):** The human-readable translation of the risk score.
  * *Possible values:* `"NORMAL"` (score <= 0.30), `"BUSY"` (score <= 0.55), `"WARNING"` (score <= 0.75), `"CRITICAL"` (score > 0.75).
* **`risk_flags` (e.g., `["overcrowding"]`):** An array of specific triggers that pushed the risk higher.
  * *Possible values:* `"overcrowding"` (density > 0.9), `"panic_movement"` (motion score > 1.2), `"sudden_surge"` (surge score > 0.5). If none are triggered, it is an empty array `[]`.
* **`severity` (e.g., "LOW"):** A backward-compatibility field mapped from the risk level, used by the UI charts.
  * *Possible values:* `"LOW"` (for Normal/Busy), `"MEDIUM"` (for Warning), `"HIGH"` (for Critical).
* **`crowd_state` (e.g., "BUSY"):** An exact copy of the `risk_level`, kept to ensure older dashboard features don't break.
* **`remark` (e.g., "Risk factors detected: Overcrowding"):** A simple, auto-generated text string sent over WebSockets to display instant UI messages. If no flags are active, it reads `"Crowd behavior within normal limits"`.

---

## 7. Backend Architecture (Core Files)

Here are the critical files running the show:

* **`video_process.py` (The Pipeline Iteration):** 
  * *Role:* The core loop. It opens the video, downsizes frames, and runs the detection/tracking algorithms.
  * *Data flow:* Raw Video Frame -> YOLO -> ByteTrack -> Frame Metrics -> MongoDB.
* **`tracking.py` (The Tracker Adapter):** 
  * *Role:* Instantiates `sv.ByteTrack`, parses YOLO predictions (`extract_person_detections`), and feeds them to the tracker to match IDs.
* **`aggregator.py` (The Statistical Smoother):** 
  * *Role:* Reads raw MongoDB frame entries, slices them into 5-second chunks, passes them to the Risk Engine, triggers Webhooks/n8n alerts, and saves aggregated results.
* **`app/services/ai_service.py` (The Intelligent Describer):**
  * *Role:* Hooks into the Groq LLM API. It feeds the aggregated risk metrics and rules into the AI to auto-generate plain-english operational insights (e.g., "Why is there an alert?").

---

## 8. UI Mapping

How does backend data become visual reality?

* **Crowd Count / Trends:** The UI fetches the aggregated 5-second window data (via the `get_analysis_results` API endpoint) to plot the historical line charts (count, violations, and abnormals).
* **Risk Level & AI Summaries:** The `SituationCard.tsx` React component polls the AI service (`/ai/{sessionId}/summary`) every 12 seconds. The AI reads the Risk Engine outputs and translates them into exactly three visual fields: **Status**, **Reason**, and **Recommended Action**.
* **Alerts Display:** When the Aggregator detects a **CRITICAL** risk, an integrated webhook pushes a real-time event. Heatmap images are rendered on the backend and mapped to the frontend interface.

---

## 9. Presentation Script (What to say)

Here is a simple, natural way to explain the flow to your audience:

> *"First, we take the live video feed and break it down frame by frame.*
> 
> *Then, we detect people using an advanced AI model called YOLOv8, which acts as our system's 'eyes'. It draws boxes around everyone it sees.*
> 
> *But just seeing people isn't enough; we need to know where they go. Then we track them using ByteTrack. This assigns a persistent ID to each person, allowing us to calculate their individual walking speeds, even if they temporarily cross paths or hide behind someone.*
> 
> *Next, we calculate system-wide metrics. By combining everyone's speed, the area they take up on screen, and the overall crowd size over a 5-second timeframe, we generate a highly accurate dataset.*
> 
> *Finally, we pass this data into our contextual Risk Engine. Because a crowded football stadium is different than a crowded restricted hallway, our Risk Engine dynamically weights the density and motion. If the algorithm detects an unnatural surge or panic movement, it instantly jumps to Critical, generating an AI summary and alerting security staff on the dashboard."*
> 

---

## 10. Live Demo Scenario: The Gallery Rush

If you are running a live demo of a gallery where people continuously pour in (0 to 250 people), here is exactly how to explain it to your audience while it happens.

### The Setup:
* **Context Location:** An Art Gallery opening.
* **Flow Type:** `"FAST_FLOW"` (Expected walking speed is high, e.g., 80 pixels/sec).
* **Goal:** `"MONITORING"` (The system balances Density 50%, Motion 30%, and Surge 20%).
* **Sensitivity:** `"HIGH"` (Multiplies final raw risk by `1.2` for early warnings).
* **Capacity:** `200` people.

### The Script (What to say during the demo):

> *"For this demonstration, we are monitoring a gallery space. We've told the system that the maximum safe capacity is 200 people. Because it's a busy exhibition, we set the 'Flow Type' to 'Fast Flow', so the system expects continuous, brisk movement. Furthermore, we've set the 'Sensitivity' to 'High' to ensure we get early warnings before it gets dangerously packed.*
> 
> *Right now, watch the crowd count rise across the 5-second aggregated windows. As the crowd hits 250 people, we are officially 25% over our safe capacity.*
> 
> *Let me show you exactly what the Risk Engine is doing behind the scenes at this exact moment:*
>
> *1. First, it calculates the **Density Score**. We are at 250 people against a capacity of 200. That gives a base density score of 1.25. (Because clustering is allowed in galleries, the engine softens this slightly behind the scenes).*
> *2. Next, it calculates the **Motion Score**. The crowd is moving at a speed of about 60, compared to our fast expected speed of 80. That gives us a motion score of 0.75.*
> *3. Finally, it calculates the **Final Risk Score**. Because our goal is 'Monitoring', the engine weights density heavily (50%) and motion moderately (30%). It adds these up, applies our High Sensitivity multiplier of 1.2... and we get a final Risk Score of roughly **0.72**.*
>
> *Because 0.72 crosses our safety threshold, you will immediately see the Risk Level jump to **WARNING** (or CRITICAL if they start moving faster). At this moment, the system is auto-capturing a heatmap and pinging the AI to generate a natural-language alert for our security staff."*
