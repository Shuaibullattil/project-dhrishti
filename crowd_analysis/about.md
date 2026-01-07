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
| **`abnormal_data_process.py`** | Analyzes movement energy to detect anomalies and energy distribution. |
| **`movement_data_present.py`** | Generates optical flow trails and stationary hotspot heatmaps. |
| **`crowd_data_present.py`**    | Plots time-series graphs for crowd count, violations, and restricted entry. |
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
**Output**: Console statistics + `processed_data/energy_distribution_original.png` & `processed_data/energy_distribution_cleaned.png`

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
5. ✅ Creates histograms showing energy distribution:
   - `energy_distribution_original.png`: Initial distribution including all data.
   - `energy_distribution_cleaned.png`: Distribution after removing statistical outliers for better clarity.
6. ✅ Suggests "abnormal threshold" = mean^1.05

**Example output**:

```
Useful movement data: 1204
Skew: 3.2
Summary: mean=145, std=89, min=0, max=520
Acceptable energy level is 151
```

---

### 3. `movement_data_present.py` - Visualization (Heatmap + Movement Tracks)

**Input**: Video file + `movement_data.csv` + tracking data  
**Output**: 2 images in `processed_data/`:

- `movement_tracks.png` - Colored trails showing the paths taken by individuals.
- `stationary_heatmap.png` - Heat regions showing where people spent most of their time (hotspots).

**What it does**:

1. ✅ Loads movement tracks from CSV.
2. ✅ Extracts frame from video for background.
3. ✅ **Movement Tracks**: Draws color-coded lines for each person's path (using gradient colors).
4. ✅ **Stationary Heatmap**: Overlays circles at points where people were stationary.
   - Circle radius = duration of stay.
   - Color intensity = accumulation of stationary points in that area.
5. ✅ Saves visualizations to the `processed_data` folder.

**Visual interpretation**:

- Bright red/yellow regions = congestion/gathering points.
- Smooth lines = steady flow; jagged or overlapping lines = congestion.

---

### 4. `crowd_data_present.py` - Time-Series Statistics Plot

**Input**: `crowd_data.csv` + `video_data.json`  
**Output**: Time-series graph in `processed_data/`:

- `crowd_statistics_time.png`: A combined plot showing various crowd metrics over time.

**What it does**:

1. ✅ Loads crowd summary statistics (Count, Violations, Anomaly Flags).
2. ✅ Maps frame numbers to actual clock time based on start time.
3. ✅ Plots:
   - **Crowd Count**: Total number of people detected.
   - **Violation Count**: Number of social distancing violations.
   - **Restricted Entry**: Highlighted regions where unauthorized entry was detected.
   - **Abnormal Activity**: Flags periods of high kinetic energy/anomalies.
4. ✅ Saves as `processed_data/crowd_statistics_time.png`.

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
  ├─→ abnormal_data_process.py  → energy_distribution_original.png + energy_distribution_cleaned.png
  ├─→ movement_data_present.py  → movement_tracks.png + stationary_heatmap.png
  └─→ crowd_data_present.py     → crowd_statistics_time.png
```

---

## Example Workflow

```powershell
# 1. Ensure config.py has correct VIDEO_CAP path
# 2. Process video (takes ~5-30 min depending on length)
python main.py
# → Creates processed_data/ folder with CSVs

# 3. Generate analysis plots
python abnormal_data_process.py    # Energy analysis (Histograms)
python movement_data_present.py    # Visualization (Tracks & Heatmap)
python crowd_data_present.py       # Statistics (Time-series graph)

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
