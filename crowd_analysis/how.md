# Abnormal Activity Detection - Comprehensive Guide

This document explains all terms and concepts used in abnormal crowd activity detection, with simple explanations and real-world scenarios.

---

## Core Concepts

### 1. **Kinetic Energy (KE)**

**What it is:**

- A measurement of how fast a person is moving
- Formula: `KE = 0.5 * speed²`
- `speed = distance / time_step` (pixels per second)

**Why we use it:**

- Fast movement = high KE = potential abnormal behavior
- Slow movement = low KE = normal behavior
- Helps distinguish between calm walking and running/panic

**Example Calculation:**

```
Person moves 10 pixels in 0.2 seconds (one sampled frame):
- speed = 10 / 0.2 = 50 pixels/second
- KE = 0.5 * 50² = 0.5 * 2500 = 1250
```

---

## Configuration Terms (from config.py)

### 2. **ABNORMAL_ENERGY**

- **Default value:** `1866`
- **What it means:** The KE threshold for a single person
- **Usage:** If a person's KE > 1866, they are marked as potentially abnormal
- **Tuning guide:**
  - **Lower value (e.g., 1000):** Detects even moderate movement as abnormal (more sensitive, more false positives)
  - **Higher value (e.g., 3000):** Only detects very fast movement (less sensitive, may miss actual anomalies)

**Example thresholds for different movements:**
| Movement Type | Distance (px/frame) | KE Value | Status |
|---|---|---|---|
| Standing still | 0 | 0 | Normal |
| Casual walk | 5 | 63 | Normal |
| Fast walk | 10 | 250 | Normal |
| Running | 15 | 563 | Normal |
| Sprinting | 20 | 1000 | Borderline |
| Panic/Fall | 30+ | 2250+ | **Abnormal** |

---

### 3. **ABNORMAL_MIN_PEOPLE**

- **Default value:** `5`
- **What it means:** Minimum crowd size before checking for abnormal behavior
- **Usage:** Only if `total people detected > 5`, we check for abnormal activity
- **Why?** A single person running is not necessarily abnormal; a crowd behavior is the concern

**Example:**

```
- 3 people detected: ABNORMAL check is SKIPPED (too few people)
- 5 people detected: ABNORMAL check is SKIPPED (need > 5)
- 6 people detected: ABNORMAL check is PERFORMED
```

---

### 4. **ABNORMAL_THRESH**

- **Default value:** `0.66` (66%)
- **What it means:** Proportion of abnormal people needed to flag the entire frame
- **Usage:** If `(number of abnormal people) / (total people) > 0.66`, the frame is abnormal
- **Tuning guide:**
  - **Lower value (e.g., 0.3):** Easier to trigger abnormal (just 30% of crowd needs to move fast)
  - **Higher value (e.g., 0.9):** Harder to trigger (90% of crowd must move fast)

**Example:**

```
Scenario 1: 10 people total, 5 moving abnormally
- Proportion = 5 / 10 = 0.5
- 0.5 < 0.66 → ABNORMAL = False (not enough people moving fast)

Scenario 2: 10 people total, 7 moving abnormally
- Proportion = 7 / 10 = 0.7
- 0.7 > 0.66 → ABNORMAL = True (crowd is behaving abnormally!)
```

---

### 5. **TIME_STEP**

- **Definition:** Time elapsed between consecutive sampled frames (in seconds)
- **For recorded video:** `TIME_STEP = DATA_RECORD_FRAME / VID_FPS`
  - Example: VIDEO FPS=25, DATA_RECORD_RATE=5 → TIME_STEP = (25/5)/25 = 0.2 seconds
- **For live camera:** `TIME_STEP = 1` second (samples taken every 1 second)
- **Impact on KE:**
  - Larger TIME_STEP = slower detected speed = lower KE (less sensitive)
  - Smaller TIME_STEP = faster detected speed = higher KE (more sensitive)

---

## Step-by-Step Detection Process

### Per-Frame Processing:

**Step 1: For each detected person:**

1. Get their centroid position (current frame and previous frame)
2. Calculate distance moved (in pixels)
3. Calculate KE = 0.5 \* (distance / TIME_STEP)²
4. If KE > ABNORMAL_ENERGY → add person's ID to `abnormal_individual` list

**Step 2: Evaluate entire crowd:**

1. Check if total people > ABNORMAL_MIN_PEOPLE
2. If yes, calculate proportion: `abnormal_people / total_people`
3. If proportion > ABNORMAL_THRESH → set `ABNORMAL = True`

**Step 3: Take action if abnormal:**

- Draw blue boxes around abnormal people
- Display "ABNORMAL ACTIVITY" warning
- Upload frame to Cloudinary (if configured)
- Record abnormal_activity=True in database/CSV

---

## Detailed Scenarios

### **Scenario 1: Calm Crowd - NO ABNORMAL**

```
Situation: Airport terminal, evening shift (20 people)
- Most people standing or sitting
- Some slowly walking to gates (very gentle movement)

Analysis per frame:
- Person 1: moves 1px → KE = 0.5 * (1/0.2)² = 12.5 (way below 1866)
- Person 2: moves 2px → KE = 0.5 * (2/0.2)² = 50 (way below 1866)
- ...
- Person 20: moves 2px → KE = 50

Result:
- abnormal_individual = [] (empty, no one exceeds KE threshold)
- Total people = 20 > ABNORMAL_MIN_PEOPLE(5) ✓
- Proportion = 0 / 20 = 0
- 0 < 0.66 → ABNORMAL = False ✓

Visual output: Green boxes around people, "Crowd count: 20" displayed
```

---

### **Scenario 2: Normal Walking - NO ABNORMAL**

```
Situation: Train station, people walking to trains normally (8 people)
- Everyone walking at normal pace
- Average displacement: 8-10 pixels per sampled frame

Analysis per frame:
- Person 1: moves 9px → KE = 0.5 * (9/0.2)² = 0.5 * 2025 = 1012.5
- Person 2: moves 10px → KE = 0.5 * (10/0.2)² = 0.5 * 2500 = 1250
- ...all people: KE between 1000-1250

Result:
- abnormal_individual = [] (no one exceeds 1866)
- Total people = 8 > ABNORMAL_MIN_PEOPLE(5) ✓
- Proportion = 0 / 8 = 0
- 0 < 0.66 → ABNORMAL = False ✓

Visual output: Green boxes, "Crowd count: 8" displayed
```

---

### **Scenario 3: Fast Walking/Jogging - MIXED**

```
Situation: Train arriving, some people rush to board (10 people)
- 2 people jogging/rushing
- 8 people walking normally

Analysis per frame:
- Jogging person 1: moves 15px → KE = 0.5 * (15/0.2)² = 0.5 * 5625 = 2812.5 ✓ EXCEEDS 1866!
- Jogging person 2: moves 14px → KE = 0.5 * (14/0.2)² = 0.5 * 4900 = 2450 ✓ EXCEEDS 1866!
- Walking person 3: moves 10px → KE = 1250 (below 1866)
- Walking person 4-10: KE around 1000-1250 (all below 1866)

Result:
- abnormal_individual = [ID_1, ID_2] (2 people flagged)
- Total people = 10 > ABNORMAL_MIN_PEOPLE(5) ✓
- Proportion = 2 / 10 = 0.2
- 0.2 < 0.66 → ABNORMAL = False ✓

Visual output: Blue boxes around 2 jogging people, but NO "ABNORMAL ACTIVITY" warning
(Not enough proportion of people are abnormal)
```

---

### **Scenario 4: Crowd Surge/Panic - ABNORMAL TRUE**

```
Situation: Major incident causes panic; people running/rushing (12 people)
- 9 people running away rapidly
- 3 people moving moderately faster

Analysis per frame:
- Running person 1: moves 25px → KE = 0.5 * (25/0.2)² = 0.5 * 15625 = 7812.5 ✓
- Running person 2: moves 24px → KE = 0.5 * (24/0.2)² = 0.5 * 14400 = 7200 ✓
- ...
- Running persons 1-9: all have KE > 3000 ✓
- Faster person 10: moves 12px → KE = 0.5 * (12/0.2)² = 1800 (below 1866)
- Moderate person 11-12: KE around 1500 (below 1866)

Result:
- abnormal_individual = [ID_1, ID_2, ID_3, ID_4, ID_5, ID_6, ID_7, ID_8, ID_9] (9 people)
- Total people = 12 > ABNORMAL_MIN_PEOPLE(5) ✓
- Proportion = 9 / 12 = 0.75
- 0.75 > 0.66 → ABNORMAL = True ✓

Visual output:
✓ Blue boxes drawn around all 9 abnormal people
✓ "ABNORMAL ACTIVITY" warning displayed
✓ Frame uploaded to Cloudinary
✓ abnormal_activity=True recorded in database
```

---

### **Scenario 5: Fall/Trip/Tracking Spike - NOT ABNORMAL**

```
Situation: One person trips and falls (8 people total)
- 1 person has sudden large movement due to fall
- 7 people walking normally

Analysis per frame:
- Falling person 1: moves 50px (centroid jumps due to fall) → KE = 0.5 * (50/0.2)² = 31250 ✓
- Walking persons 2-8: move 8-10px → KE around 800-1250

Result:
- abnormal_individual = [ID_1] (only 1 person)
- Total people = 8 > ABNORMAL_MIN_PEOPLE(5) ✓
- Proportion = 1 / 8 = 0.125
- 0.125 < 0.66 → ABNORMAL = False ✓

Visual output:
- Blue box around falling person only
- BUT NO "ABNORMAL ACTIVITY" warning (not enough people)
- Can still be useful to review person with high KE
```

---

### **Scenario 6: Small Group Alert - NO CHECK**

```
Situation: 3 people running (e.g., kids playing)
- All 3 moving fast

Analysis per frame:
- Person 1: KE = 3000 ✓
- Person 2: KE = 2500 ✓
- Person 3: KE = 2800 ✓

Result:
- abnormal_individual = [ID_1, ID_2, ID_3] (all 3 flagged)
- Total people = 3 ≤ ABNORMAL_MIN_PEOPLE(5) ✗

ABNORMAL CHECK IS SKIPPED!
- ABNORMAL stays False (due to min people guard)

Visual output: Blue boxes around 3 people, but NO warning
(Too few people to care about)
```

---

### **Scenario 7: Live Camera Mode - LESS SENSITIVE**

```
Situation: Same panic scenario, but using live camera feed (TIME_STEP=1.0)

Analysis per frame:
- Running person: moves 25px in 1 second
- KE = 0.5 * (25/1.0)² = 0.5 * 625 = 312.5 ✓ (NOW MUCH LOWER!)

Comparison:
- Video (TIME_STEP=0.2): KE = 7812.5 (very high)
- Camera (TIME_STEP=1.0): KE = 312.5 (moderate)

Result:
- Many people who would be flagged in video are NOT flagged in live feed
- Less sensitive to rapid movement
- Fewer false positives but might miss actual anomalies

Lesson: Live camera mode is intentionally less sensitive
```

---

### **Scenario 8: Camera Jitter/Tracking Artifact - FALSE POSITIVE**

```
Situation: Camera shakes or sudden camera pan; tracking IDs flicker
- No actual crowd anomaly
- But tracking system shows sudden large centroid shifts

Analysis per frame:
- Camera shake causes tracking update
- Person 1: centroid shifts 40px (due to camera, not person movement)
- Person 2: centroid shifts 35px
- ... all people show large shifts

Result:
- All detected people have artificially high KE
- abnormal_individual = [many IDs]
- Proportion >> 0.66 → ABNORMAL = True (FALSE POSITIVE!)

Visual output: False warning displayed

Mitigation:
- Add global motion compensation (detect camera movement)
- Apply smoothing to centroid positions
- Require consecutive frames of abnormality before confirming
```

---

## Tuning Guide

### To Reduce False Positives (fewer warnings):

1. **Increase ABNORMAL_ENERGY:** Require faster movement (e.g., 2500)
2. **Increase ABNORMAL_THRESH:** Require more people moving abnormally (e.g., 0.8)
3. **Increase ABNORMAL_MIN_PEOPLE:** Require larger crowds (e.g., 10)

### To Increase Sensitivity (catch more anomalies):

1. **Decrease ABNORMAL_ENERGY:** Detect even moderate fast movement (e.g., 1000)
2. **Decrease ABNORMAL_THRESH:** Trigger with fewer abnormal people (e.g., 0.5)
3. **Decrease ABNORMAL_MIN_PEOPLE:** Check small crowds too (e.g., 3)

### Example Tuning for Different Scenarios:

| Scenario                | ABNORMAL_ENERGY | ABNORMAL_THRESH | ABNORMAL_MIN_PEOPLE |
| ----------------------- | --------------- | --------------- | ------------------- |
| High-security (airport) | 1200            | 0.5             | 5                   |
| Normal monitoring       | 1866            | 0.66            | 5                   |
| Loose monitoring        | 3000            | 0.8             | 10                  |

---

## Key Takeaways

1. **Abnormal detection is two-level:**

   - Per-person: Is this individual moving abnormally? (KE > ABNORMAL_ENERGY)
   - Per-frame: Is the crowd behaving abnormally? (proportion > ABNORMAL_THRESH)

2. **Both thresholds must be satisfied:**

   - If only 1-2 people run fast, it's not a crowd issue → no warning
   - If 10+ people walk calmly but one trips, it's not a crowd issue → no warning

3. **TIME_STEP matters:**

   - Video sampling (TIME_STEP ≈ 0.2s) is more sensitive
   - Live camera (TIME_STEP = 1s) is less sensitive

4. **False positives possible:**

   - Camera artifacts, tracking errors, ID switches can cause them
   - Mitigate with motion compensation or temporal smoothing

5. **Configuration is key:**
   - No one-size-fits-all threshold
   - Adjust based on your environment and tolerance for alerts

---

## Code References

### Where to find these terms:

- **config.py:** ABNORMAL_ENERGY, ABNORMAL_THRESH, ABNORMAL_MIN_PEOPLE, DATA_RECORD_RATE
- **util.py:** `kinetic_energy()` function (KE calculation)
- **video_process.py:** Main logic for per-frame abnormal detection (lines 192-218)

### How to modify:

Edit `config.py` to change thresholds without touching detection logic.
