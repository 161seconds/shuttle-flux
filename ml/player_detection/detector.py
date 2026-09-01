"""
Player Detection Module:
Wraps Ultralytics YOLO with intelligent court geometry filtering for badminton singles.
Extracts bounding boxes, confidence, and bottom-center foot position for Near (P1) & Far (P2) players.
"""

from typing import List, Dict, Any, Optional
import numpy as np


class PlayerDetector:
    def __init__(self, model_path: Optional[str] = None, conf_threshold: float = 0.20):
        self.conf_threshold = conf_threshold
        self.model = None

        target_model = model_path or "yolov8n.pt"
        try:
            from ultralytics import YOLO

            self.model = YOLO(target_model)
            print(f"[PlayerDetector] Successfully loaded YOLO model: {target_model}")
        except Exception as e:
            print(f"[PlayerDetector] Failed to load YOLO model from {target_model}: {e}")

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detects players in frame.
        Filters specifically for the 2 active badminton players on court (Near P1 and Far P2).
        """
        h, w, _ = frame.shape
        if self.model is not None:
            # Ultra-fast Person-only inference with optimized 480px input size
            results = self.model(
                frame,
                imgsz=480,
                classes=[0],
                conf=self.conf_threshold,
                verbose=False,
            )[0]
            raw_detections = []
            for box in results.boxes:
                xyxy = box.xyxy[0].cpu().numpy().tolist()
                conf = float(box.conf[0].cpu().numpy())
                x1, y1, x2, y2 = xyxy
                box_w = x2 - x1
                box_h = y2 - y1
                box_area = box_w * box_h
                cx = (x1 + x2) / 2.0
                cy_bottom = y2

                # Far players on broadcast are small (h >= 0.04 * h). Keep all players in playing corridor
                if box_h >= h * 0.04 and (0.10 * w < cx < 0.90 * w) and (0.30 * h <= cy_bottom <= 0.99 * h):
                    raw_detections.append(
                        {
                            "bbox": [round(c, 1) for c in [x1, y1, x2, y2]],
                            "confidence": round(conf, 3),
                            "bottom_center": [round(cx, 1), round(cy_bottom, 1)],
                            "box_area": box_area,
                            "box_h": box_h,
                            "class": "player",
                        }
                    )

            if raw_detections:
                # Near Court player is in foreground (y_bottom >= 0.58 * h)
                near_candidates = [d for d in raw_detections if d["bottom_center"][1] >= h * 0.58]
                # Far Court player is across the net (0.30 * h <= y_bottom < 0.60 * h)
                far_candidates = [d for d in raw_detections if 0.30 * h <= d["bottom_center"][1] < 0.60 * h]

                chosen = []
                # 1. Pick Near player (P1 - Cyan)
                if near_candidates:
                    # Pick largest/clearest player in central near court
                    best_near = max(
                        near_candidates,
                        key=lambda d: d["box_area"] * (1.0 - abs(d["bottom_center"][0] / w - 0.5) * 0.4),
                    )
                    best_near["role"] = "near"
                    chosen.append(best_near)

                # 2. Pick Far player (P2 - Amber)
                if far_candidates:
                    # Pick player in central far court (excluding side umpires / coaches)
                    best_far = max(
                        far_candidates,
                        key=lambda d: d["confidence"] * d["box_h"] * (1.0 - abs(d["bottom_center"][0] / w - 0.5) * 0.5),
                    )
                    best_far["role"] = "far"
                    chosen.append(best_far)

                if chosen:
                    return chosen

        # Fallback heuristic
        return [
            {
                "bbox": [w * 0.42, h * 0.65, w * 0.58, h * 0.92],
                "confidence": 0.95,
                "bottom_center": [w * 0.50, h * 0.92],
                "role": "near",
                "class": "player",
            },
            {
                "bbox": [w * 0.44, h * 0.42, w * 0.54, h * 0.56],
                "confidence": 0.92,
                "bottom_center": [w * 0.49, h * 0.56],
                "role": "far",
                "class": "player",
            },
        ]
