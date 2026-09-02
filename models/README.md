# Model files

Model binaries are intentionally excluded from Git. Put optional runtime artifacts here:

- `sam3.pt` - authorized Meta SAM 3 checkpoint
- `yolov8n.onnx` - ONNX export from `scripts/export_models.py`
- `yolov8n.engine` - TensorRT export generated on the target GPU
- `osnet_x0_25.onnx` - OSNet ReID embedding model
- `yolo11n-pose.pt` - public Ultralytics body-pose model (auto-download supported)
- `racket-pose.pt` - optional custom racket model with handle/head/tip keypoints

`yolov8n.pt` at the repository root remains the default PyTorch fallback. Ultralytics can download it when network access is available, or you can place the file there manually.
