# Crowd-Analysis Project Overview

## What is it?

A **real-time crowd monitoring and analysis system** designed for CCTV and surveillance. It detects, tracks, and analyzes crowds to identify:

- 👥 Human count and crowd density
- 🚨 Abnormal crowd activity (high energy/dangerous situations)
- 📏 Social distance violations
- 🚪 Restricted area entries
- 🔄 Movement patterns (optical flow, heatmaps)

## Core Technology Stack

- **Human Detection**: YOLOv4-tiny (fast, lightweight object detection)
- **Person Tracking**: Deep SORT (tracks individual identities across frames)
- **Movement Analysis**: Optical flow & kinetic energy computation
- **Visualization**: OpenCV, Matplotlib

---

## Important Files & Directory Structure

| File                           | Purpose                                                                                   |
| ------------------------------ | ----------------------------------------------------------------------------------------- |
| **`config.py`**                | Configuration hub - set video path, detection thresholds, anomaly sensitivity, frame size |
| **`main.py`**                  | **Entry point** - processes video frame-by-frame using YOLO + Deep SORT, outputs CSV/JSON |
| **`video_process.py`**         | Core video processing logic: frame analysis, detection, tracking, data recording          |
| **`tracking.py`**              | YOLO detection wrapper                                                                    |
| **`util.py`**                  | Helper functions (distance calc, energy, progress bar)                                    |
| **`colors.py`**                | Color utilities for visualization                                                         |
| **`abnormal_data_process.py`** | Analyzes movement energy to detect anomalies                                              |
| **`crowd_data_present.py`**    | Generates heatmaps & optical flow visualizations                                          |
| **`movement_data_present.py`** | Plots crowd count, violations, restricted entries over time                               |
| **`deep_sort/`**               | Tracking algorithm (person re-identification)                                             |
| **`model_data/`**              | Pre-trained neural network models (YOLO weights, Deep SORT encoder)                       |
| **`YOLOv4-tiny/`**             | YOLO weights & config files                                                               |
| **`processed_data/`**          | Output folder with CSV/JSON results                                                       |

---

## What Each Script Does

### 1. `main.py` - Video Processing (The Pipeline)

**Input**: Video file from `config.py`  
**Output**: 2 CSV files + 1 JSON file in `processed_data/`

**Step-by-step process**:

1. ✅ Loads YOLOv4-tiny (object detector)
2. ✅ Initializes Deep SORT tracker
3. ✅ **For each frame in video**:
   - Detects humans using YOLO
   - Tracks each person with a unique ID
   - Records frame data (timestamp, human count, violations, etc.)
4. ✅ Outputs:
   - `movement_data.csv` - tracks of each person (entry/exit times + position coordinates)
   - `crowd_data.csv` - per-frame summary (time, human count, violations, anomalies)
   - `video_data.json` - metadata (FPS, frame size, timestamps)

**How long it takes**: Depends on video length; processes at ~X FPS (shown at end)

---

### 2. `abnormal_data_process.py` - Anomaly Detection Analysis

**Input**: `processed_data/movement_data.csv` + `video_data.json`  
**Output**: Console statistics + `energy_distribution.png` (histogram)

**What it does**:

1. ✅ Extracts movement tracks from tracking data
2. ✅ Calculates **kinetic energy** for each movement segment:
   - Energy = 0.5 × speed²
   - Higher energy = faster movement = potentially dangerous crowd
3. ✅ Identifies stationary points (people standing still)
4. ✅ Generates statistics:
   - Energy mean, median, std dev
   - Skewness & Kurtosis (outlier detection)
   - Removes extreme outliers if skewness > 7.5
5. ✅ Creates histogram showing energy distribution
6. ✅ Suggests "abnormal threshold" = mean^1.05

**Example output**:

```
Useful movement data: 1204
Skew: 3.2
Summary: mean=145, std=89, min=0, max=520
Acceptable energy level is 151
```

---

### 3. `crowd_data_present.py` - Visualization (Heatmap + Optical Flow)

**Input**: Video file + `crowd_data.csv` + tracking data  
**Output**: 2 images:

- `optical_flow.png` - colored trails showing where people moved
- `heatmap.png` - heat regions showing where people spent most time (red = stationary hotspots)

**What it does**:

1. ✅ Loads crowd statistics from CSV
2. ✅ Reads video and extracts movement tracks
3. ✅ **Optical Flow**: Draws colored lines for each person's path (gradient from blue→orange)
4. ✅ **Heatmap**: Overlays semi-transparent circles at stationary points
   - Circle radius = how long person stayed
   - Color intensity = number of people at that spot
5. ✅ Saves visualizations

**Visual interpretation**:

- Bright red heatmap regions = congestion/gathering points
- Straight optical flow lines = organized movement
- Curved/tangled lines = chaotic movement = anomaly

---

### 4. `movement_data_present.py` - Time-Series Summary Plot

**Input**: `movement_data.csv` + `crowd_data.csv` + video  
**Output**: 4 subplots over time:

**Subplot 1: Crowd Count** - Number of people in frame over time  
**Subplot 2: Social Distance Violations** - How many people violating 50px distance rule  
**Subplot 3: Restricted Entry** - Entries to marked forbidden areas  
**Subplot 4: Abnormal Activity Flag** - When crowd energy exceeds threshold

**What it does**:

1. ✅ Loads crowd statistics from CSV
2. ✅ Splits time axis into frames
3. ✅ Plots 4 metrics with time-based x-axis
4. ✅ Highlights anomalous periods
5. ✅ Saves as `movement_summary.png`

**Example interpretation**:

- Crowd count spikes → many people present
- Violations spike → people too close together (pandemic concern)
- Abnormal activity spikes → chaotic movement detected

---

## Data Flow Diagram

```
📹 Video (config.py)
  ↓
┌─────────────────────────────┐
│   main.py (PROCESS)         │
│ - YOLO detection            │
│ - Deep SORT tracking        │
│ - Frame-by-frame analysis   │
└─────────────────────────────┘
  ↓↓↓ Outputs ↓↓↓
  ├─→ movement_data.csv (track coordinates)
  ├─→ crowd_data.csv (count, violations, anomalies)
  └─→ video_data.json (metadata)

  ↓↓↓ Analysis ↓↓↓
  ├─→ abnormal_data_process.py  → energy_distribution.png + statistics
  ├─→ crowd_data_present.py     → optical_flow.png + heatmap.png
  └─→ movement_data_present.py  → movement_summary.png
```

---

## Example Workflow

```powershell
# 1. Ensure config.py has correct VIDEO_CAP path
# 2. Process video (takes ~5-30 min depending on length)
python main.py
# → Creates processed_data/ folder with CSVs

# 3. Generate analysis plots (takes ~1-5 min)
python abnormal_data_process.py    # Energy analysis
python crowd_data_present.py       # Heatmap & optical flow
python movement_data_present.py    # Time-series plot

# 4. View outputs in processed_data/ + current folder
```

---

## Configuration (`config.py`) Quick Reference

| Setting            | Default             | Purpose                                        |
| ------------------ | ------------------- | ---------------------------------------------- |
| `VIDEO_CAP`        | `"video/Crowd.mp4"` | Input video path                               |
| `IS_CAM`           | `False`             | Use webcam instead of file                     |
| `DATA_RECORD_RATE` | `5`                 | Record data every N frames                     |
| `FRAME_SIZE`       | `1080`              | Resize video to this width (faster processing) |
| `SOCIAL_DISTANCE`  | `50`                | Violation threshold in pixels                  |
| `ABNORMAL_CHECK`   | `True`              | Enable anomaly detection                       |
| `ABNORMAL_ENERGY`  | `1866`              | Energy level threshold for flagging            |
| `MIN_CONF`         | `0.3`               | YOLO confidence threshold                      |

This is a **complete surveillance analytics pipeline** for monitoring crowd behavior in real-time or batch mode! 🎯
