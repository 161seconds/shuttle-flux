"""Badminton racket detection with a custom-model path and COCO fallback."""

import os
from pathlib import Path
from typing import Any, Dict, List

import numpy as np


class RacketDetector:
    def __init__(self, shared_model: Any = None, device: str = "cpu"):
        workspace_root = Path(__file__).resolve().parents[2]
        self.model_path = Path(
            os.getenv("RACKET_MODEL_PATH", workspace_root / "models" / "racket-pose.pt")
        )
        self.enabled = os.getenv("ENABLE_RACKET_DETECTION", "1") == "1"
        self.device = device
        self.shared_model = shared_model
        self.model = None
        self.using_custom_model = self.model_path.is_file()

    def _load(self) -> bool:
        if not self.enabled:
            return False
        if self.using_custom_model and self.model is None:
            try:
                from ultralytics import YOLO

                self.model = YOLO(str(self.model_path))
                print(f"[Racket] Loaded custom racket model: {self.model_path}")
            except Exception as exc:
                print(f"[Racket] Custom model failed, using COCO fallback: {exc}")
                self.using_custom_model = False
        return self.model is not None or self.shared_model is not None

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        if not self._load():
            return []

        model = self.model if self.using_custom_model else self.shared_model
        options: Dict[str, Any] = {
            "source": frame,
            "conf": float(os.getenv("RACKET_CONFIDENCE", "0.08")),
            "imgsz": int(
                os.getenv("RACKET_IMAGE_SIZE", "960")
            ),
            "device": self.device,
            "verbose": False,
        }
        if not self.using_custom_model:
            # COCO class 38 is tennis racket and provides a useful badminton fallback.
            options["classes"] = [38]

        try:
            result = model.predict(**options)[0]
        except Exception as exc:
            print(f"[Racket] Frame inference failed: {exc}")
            return []

        detections: List[Dict[str, Any]] = []
        pose_data = None
        if getattr(result, "keypoints", None) is not None:
            pose_data = result.keypoints.data.detach().cpu().numpy()

        boxes = result.boxes
        for index, box in enumerate(boxes if boxes is not None else []):
            x1, y1, x2, y2 = box.xyxy[0].detach().cpu().numpy().astype(float).tolist()
            confidence = float(box.conf[0].detach().cpu().item())
            detection: Dict[str, Any] = {
                "bbox": [round(value, 1) for value in (x1, y1, x2, y2)],
                "center": [round((x1 + x2) / 2.0, 1), round((y1 + y2) / 2.0, 1)],
                "confidence": round(confidence, 3),
                "source": "custom-racket-pose" if self.using_custom_model else "coco-racket",
            }
            if pose_data is not None and index < len(pose_data):
                names = ("handle", "head_center", "tip")
                detection["keypoints"] = {
                    name: [round(float(x), 1), round(float(y), 1), round(float(conf), 3)]
                    for name, (x, y, conf) in zip(names, pose_data[index])
                }
                handle = detection["keypoints"].get("handle")
                head = detection["keypoints"].get("head_center")
                if handle and head and handle[2] >= 0.2 and head[2] >= 0.2:
                    detection["orientation_degrees"] = round(
                        float(np.degrees(np.arctan2(head[1] - handle[1], head[0] - handle[0]))),
                        1,
                    )
            detections.append(detection)
        return detections
