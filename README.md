# Project Dhrishti — Crowd Analysis Package

This folder contains a reorganized copy of the Crowd-Analysis code so contributors can clone and use it easily.

## Quick summary

- Purpose: Detect, track and analyze crowd behaviour (abnormal activity, social distancing, heatmaps).
- Requires: Python 3.9 (recommended). Use a virtual environment.

## Install

1. Install Python 3.9 and add to PATH.
2. Create and activate a venv inside the project root:

```powershell
py -3.9 -m venv venv
.\\venv\\Scripts\\Activate.ps1
python -m pip install --upgrade pip
pip install -r crowd_analysis/requirements.txt
```

## Files moved

- `crowd_analysis/` — code and scripts (main, video_process, analysis and visualizers)
- `crowd_analysis/requirements.txt` — pinned deps (same as original repo)

### Not included by default

The following large assets should be copied from the original repo or downloaded manually:

- `deep_sort/` (tracking code)
- `model_data/` (DeepSORT encoder model)
- `YOLOv4-tiny/` (YOLO weights & cfg)

You can copy them from the original `Crowd-Analysis` folder or add as submodules.

## Usage (example)

1. Configure `crowd_analysis/config.py` — set `VIDEO_CONFIG["VIDEO_CAP"]` to your input video path.
2. Run the pipeline to process the video and store outputs:

```powershell
cd project-dhrishti
python -m crowd_analysis.main
```

3. Generate visualizations and reports:

```powershell
python crowd_analysis/abnormal_data_process.py
python crowd_analysis/crowd_data_present.py
python crowd_analysis/movement_data_present.py
```

## Workflow explanation (simple)

1. `main.py` runs detection + tracking and writes results to `processed_data/`.
2. Analysis scripts (`abnormal_data_process.py`) compute energy and flag abnormal segments.
3. Visualization scripts produce heatmaps, optical flow and time-series plots.

## How to send alerts (next steps)

The current code flags abnormal frames (`ABNORMAL`) but does not send notifications. To integrate alerts, add a small module (`alerts.py`) and call `alerts.send_webhook(...)` when the `ABNORMAL` flag is triggered in `video_process.py`. Implement cooldown to avoid repeated alerts.

## .gitignore and recommendations

- Use Python 3.9 for best compatibility with pinned packages.
- Keep heavy assets (YOLO weights, DeepSORT model) out of git and share them separately.
