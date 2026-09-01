"""
Shuttlecock Detection Module:
High-resolution small-object detector for badminton shuttlecock.
"""

from typing import Dict, Any, Optional
import numpy as np


class ShuttleDetector:
    def __init__(self, model_path: Optional[str] = None, conf_threshold: float = 0.25):
        self.conf_threshold = conf_threshold
        self.model = None

        if model_path:
            try:
                from ultralytics import YOLO

                self.model = YOLO(model_path)
            except Exception as e:
                print(f"[ShuttleDetector] Failed to load model {model_path}: {e}")

    def detect(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Detects shuttlecock in frame.
        Returns: Dict with 'center': [x, y], 'bbox': [x1, y1, x2, y2], 'confidence': float
        """
        if self.model is not None:
            results = self.model(frame, conf=self.conf_threshold, verbose=False)[0]
            best_box = None
            best_conf = 0.0

            for box in results.boxes:
                conf = float(box.conf[0].cpu().numpy())
                if conf > best_conf:
                    best_conf = conf
                    best_box = box.xyxy[0].cpu().numpy().tolist()

            if best_box is not None:
                x1, y1, x2, y2 = best_box
                return {
                    "bbox": [round(c, 1) for c in [x1, y1, x2, y2]],
                    "center": [round((x1 + x2) / 2.0, 1), round((y1 + y2) / 2.0, 1)],
                    "confidence": round(best_conf, 3),
                    "visible": True,
                }

        # Fallback simulation/heuristic
        return None
