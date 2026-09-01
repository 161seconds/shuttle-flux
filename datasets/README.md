# Datasets Directory

This folder contains dataset configurations, split definitions, and annotation guides.

## Guidelines
- Do NOT commit heavy raw video files or full image datasets to git.
- Split data **by video sequence** (e.g., Video 1 & 2 for Train, Video 3 for Val, Video 4 for Test) to avoid data leakage.
- Keep YAML configs for Ultralytics YOLO inside `datasets/configs/`.
