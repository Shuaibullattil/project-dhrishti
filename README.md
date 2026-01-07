# Project Dhrishti — Crowd Analysis Package

- Purpose: Detect, track and analyze crowd behaviour (abnormal activity, social distancing, heatmaps).
- Requires: Python 3.9 (recommended). Use a virtual environment.

## Install

1. Install Python 3.9 and add to PATH.
2. Create and activate a venv inside the project root:

```powershell
py -3.9 -m venv venv
.\\venv\\Scripts\\Activate
python -m pip install --upgrade pip
pip install -r crowd_analysis/requirements.txt
```



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
