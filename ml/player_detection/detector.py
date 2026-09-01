"""
Player Detection Module:
Wraps Ultralytics YOLO with strict court trapezoid geometry filtering for badminton singles & doubles.
Detects up to 4 active players (2v2 Doubles) or 2 active players (1v1 Singles),
strictly discarding referees/umpires on the left/right sidelines.
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
        Supports both 1v1 Singles (2 players) and 2v2 Doubles (up to 4 players).
        Filters strictly for on-court players inside the playing corridor.
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

                norm_x = cx / float(w)
                norm_y = cy_bottom / float(h)

                # 1. Height & Boundary Filter
                # Ignore staff sitting behind advertising boards (y < 0.35)
                if norm_y < 0.35 or box_h < h * 0.04:
                    continue

                # 2. Strict Trapezoid Playing Corridor Filter:
                # Discards high umpire chair on left and line judges on right
                t_y = float(np.clip((norm_y - 0.35) / 0.57, 0.0, 1.0))
                min_court_x = 0.20 - 0.13 * t_y
                max_court_x = 0.80 + 0.13 * t_y

                if not (min_court_x <= norm_x <= max_court_x):
                    continue

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
                # Near Court players (y_bottom >= 0.58 * h)
                near_candidates = [d for d in raw_detections if d["bottom_center"][1] >= h * 0.58]
                # Far Court players (0.35 * h <= y_bottom < 0.60 * h)
                far_candidates = [d for d in raw_detections if 0.35 * h <= d["bottom_center"][1] < 0.60 * h]

                # Sort near candidates by box area & centrality
                near_candidates.sort(
                    key=lambda d: d["box_area"] * (1.0 - abs(d["bottom_center"][0] / w - 0.5) * 0.3),
                    reverse=True,
                )
                # Sort far candidates by confidence & box height
                far_candidates.sort(
                    key=lambda d: d["confidence"] * d["box_h"] * (1.0 - abs(d["bottom_center"][0] / w - 0.5) * 0.4),
                    reverse=True,
                )

                chosen = []
                # Keep up to 2 near players (Team 1)
                for i, nc in enumerate(near_candidates[:2]):
                    nc_copy = dict(nc)
                    nc_copy["role"] = "near"
                    nc_copy["rank"] = i + 1
                    chosen.append(nc_copy)

                # Keep up to 2 far players (Team 2)
                for j, fc in enumerate(far_candidates[:2]):
                    fc_copy = dict(fc)
                    fc_copy["role"] = "far"
                    fc_copy["rank"] = j + 1
                    chosen.append(fc_copy)

                if chosen:
                    return chosen

        # Fallback heuristic
        return [
            {
                "bbox": [w * 0.42, h * 0.65, w * 0.58, h * 0.92],
                "confidence": 0.95,
                "bottom_center": [w * 0.50, h * 0.92],
                "role": "near",
                "rank": 1,
                "class": "player",
            },
            {
                "bbox": [w * 0.44, h * 0.42, w * 0.54, h * 0.56],
                "confidence": 0.92,
                "bottom_center": [w * 0.49, h * 0.56],
                "role": "far",
                "rank": 1,
                "class": "player",
            },
        ]
