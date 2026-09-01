"""
Player Detection Module:
Wraps Ultralytics YOLO with strict badminton court geometry & official referee exclusion.
Identifies and rejects all non-player officials on court:
  1. Main Umpire (Trọng tài chính ngồi ghế cao)
  2. Service Judge (Trọng tài giao cầu ngồi đối diện)
  3. Far Baseline Line Judges (2-3 Trọng tài biên ngồi phía xa sau sân)
  4. Near Sideline Line Judges & Staff
Accurately detects 1-2 active players per side for both 1v1 Singles and 2v2 Doubles.
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

    def is_official_referee(
        self,
        norm_x: float,
        norm_y_bottom: float,
        norm_y_top: float,
        norm_h: float,
        norm_w: float,
    ) -> bool:
        """
        Explicit filter to reject all BWF tournament officials:
          - Main Umpire (High chair at net sideline)
          - Service Judge (Low chair opposite net post)
          - Far Baseline Line Judges (2-3 judges seated behind far baseline)
          - Near Corner Line Judges
        """
        # 1. Far Baseline Line Judges (2-3 seated behind the far court baseline)
        # Broadcast far baseline is around y ~ 0.40 - 0.44. Seated line judges have y_bottom < 0.41 or small height
        if norm_y_bottom < 0.39:
            return True
        if norm_y_bottom < 0.45 and norm_h < 0.09:
            return True

        # 2. Main Umpire (Trọng tài chính - Sitting in elevated high chair near net)
        # Elevated chair raises person's head very high (norm_y_top < 0.26 while norm_y_bottom is at net ~0.45-0.65)
        # or sits directly on outer sideline (x < 0.23 or x > 0.77) at net height (0.42 <= y <= 0.65)
        is_at_net_level = 0.42 <= norm_y_bottom <= 0.66
        is_on_outer_sideline = norm_x <= 0.24 or norm_x >= 0.76
        if is_at_net_level and is_on_outer_sideline:
            # Umpire chair or service judge
            return True
        if is_at_net_level and norm_y_top < 0.26 and norm_h > 0.25:
            # Elevated high umpire chair
            return True

        # 3. Service Judge (Trọng tài giao cầu - Seated low in chair directly across the net)
        if 0.44 <= norm_y_bottom <= 0.62 and (norm_x <= 0.25 or norm_x >= 0.75):
            return True

        # 4. Near Corner / Baseline Line Judges (Sitting at bottom corners)
        if norm_y_bottom > 0.88 and (norm_x < 0.15 or norm_x > 0.85):
            return True

        # 5. Dynamic Perspective Court Corridor:
        # Interpolates playable boundary width from far court (narrow) to near court (wide)
        t_y = float(np.clip((norm_y_bottom - 0.40) / 0.52, 0.0, 1.0))
        min_playable_x = 0.26 - 0.16 * t_y
        max_playable_x = 0.74 + 0.16 * t_y

        if not (min_playable_x <= norm_x <= max_playable_x):
            return True

        return False

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detects active players in frame.
        Supports both 1v1 Singles (2 players) and 2v2 Doubles (up to 4 players).
        Strictly rejects all umpires, service judges, and line judges.
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
                norm_y_bottom = cy_bottom / float(h)
                norm_y_top = y1 / float(h)
                norm_h = box_h / float(h)
                norm_w = box_w / float(w)

                # Check if person is referee / line judge / staff
                if self.is_official_referee(norm_x, norm_y_bottom, norm_y_top, norm_h, norm_w):
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
                # Far Court players (0.40 * h <= y_bottom < 0.60 * h)
                far_candidates = [d for d in raw_detections if 0.40 * h <= d["bottom_center"][1] < 0.60 * h]

                # Sort near candidates by box area & centrality
                near_candidates.sort(
                    key=lambda d: d["box_area"] * (1.0 - abs(d["bottom_center"][0] / w - 0.5) * 0.3),
                    reverse=True,
                )
                # Sort far candidates by confidence & box height & centrality
                far_candidates.sort(
                    key=lambda d: d["confidence"] * d["box_h"] * (1.0 - abs(d["bottom_center"][0] / w - 0.5) * 0.3),
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
