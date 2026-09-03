"""
Player Detection Module:
Wraps Ultralytics YOLO with strict badminton court geometry & official referee exclusion.
Identifies and rejects all non-player officials on court:
  1. Main Umpire (Trọng tài chính ngồi ghế cao)
  2. Service Judge (Trọng tài giao cầu ngồi đối diện)
  3. Far Baseline Line Judges (2-3 Trọng tài biên ngồi phía xa sau sân)
  4. Near Sideline Line Judges & Staff
  5. Advertising board area personnel
Accurately detects 1-2 active players per side for both 1v1 Singles and 2v2 Doubles.

Changes:
- YOLO inference resolution increased from 480→640 for better accuracy
- Confidence threshold raised from 0.20→0.30 to reduce false positives
- Tighter dynamic corridor at net level to reject advertising area personnel
- Added minimum bounding box height gate (norm_h >= 0.10) to reject small distant staff
- Added top-N confidence gating: keep only top 2 (singles) or top 4 (doubles) detections
"""

from typing import List, Dict, Any, Optional
import os
import numpy as np

from ml.runtime.capabilities import resolve_yolo_runtime


class PlayerDetector:
    def __init__(self, model_path: Optional[str] = None, conf_threshold: float = 0.18):
        self.conf_threshold = conf_threshold
        self.model = None
        self.runtime_backend = "unavailable"
        self.device = "cpu"
        self.fallback_model_path = model_path or os.getenv("YOLO_MODEL_PATH", "yolov8n.pt")

        target_model, backend, device = resolve_yolo_runtime(model_path or "yolov8n.pt")
        self.model_path = target_model
        try:
            from ultralytics import YOLO

            self.model = YOLO(target_model)
            self.runtime_backend = backend
            self.device = device
            print(
                f"[PlayerDetector] Loaded YOLO model: {target_model} "
                f"(backend={backend}, device={device})"
            )
        except Exception as e:
            print(f"[PlayerDetector] Failed to load YOLO model from {target_model}: {e}")

    def _predict(self, frame: np.ndarray):
        options = {
            "imgsz": int(os.getenv("PLAYER_IMAGE_SIZE", "960")),
            "classes": [0],
            "conf": self.conf_threshold,
            "device": self.device,
            "verbose": False,
        }
        if self.runtime_backend == "pytorch" and self.device != "cpu":
            options["half"] = True
        return self.model(frame, **options)[0]

    def _predict_with_fallback(self, frame: np.ndarray):
        try:
            return self._predict(frame)
        except Exception as exc:
            print(f"[PlayerDetector] {self.runtime_backend} inference failed: {exc}")

        try:
            from ultralytics import YOLO

            if self.runtime_backend != "pytorch":
                self.model = YOLO(self.fallback_model_path)
                self.runtime_backend = "pytorch"
                print(f"[PlayerDetector] Falling back to PyTorch: {self.fallback_model_path}")
            elif self.device == "cpu":
                self.model = None
                self.runtime_backend = "unavailable"
                return None

            if self.device != "cpu":
                try:
                    return self._predict(frame)
                except Exception as exc:
                    print(f"[PlayerDetector] CUDA inference failed, falling back to CPU: {exc}")
                    self.device = "cpu"
            return self._predict(frame)
        except Exception as exc:
            print(f"[PlayerDetector] All inference backends failed: {exc}")
            self.model = None
            self.runtime_backend = "unavailable"
            return None

    def get_runtime_info(self) -> Dict[str, Any]:
        return {
            "backend": self.runtime_backend,
            "device": self.device,
            "model_path": self.model_path,
        }

    def is_official_referee(
        self,
        norm_x: float,
        norm_y_bottom: float,
        norm_y_top: float,
        norm_h: float,
        norm_w: float,
    ) -> bool:
        """
        Explicit filter to reject all BWF tournament officials and non-player personnel:
          - Main Umpire (High chair at net sideline)
          - Service Judge (Low chair opposite net post)
          - Far Baseline Line Judges (2-3 judges seated behind far baseline)
          - Near Corner Line Judges
          - Advertising area personnel (left/right of court at net level)
        """
        # 0. Minimum height gate: real players are tall enough in frame
        # This filters out very small/distant staff and audience members
        if norm_h < 0.10:
            return True

        # 1. Far Baseline Line Judges (2-3 seated behind the far court baseline)
        # Broadcast far baseline is around y ~ 0.40 - 0.44. Seated line judges have y_bottom < 0.41 or small height
        if norm_y_bottom < 0.39:
            return True
        if norm_y_bottom < 0.45 and norm_h < 0.12:
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

        # 5. Advertising board area personnel (people standing near LED banners at net level)
        # This catches people near the HSBC/sponsor banners on the sides of the court
        if 0.42 <= norm_y_bottom <= 0.72 and (norm_x < 0.28 or norm_x > 0.72):
            return True

        # 6. Dynamic Perspective Court Corridor:
        # Interpolates playable boundary width from far court (narrow) to near court (wide)
        # Tightened: far court starts at x=0.28-0.72, expands to x=0.12-0.88 at near baseline
        t_y = float(np.clip((norm_y_bottom - 0.40) / 0.52, 0.0, 1.0))
        min_playable_x = 0.28 - 0.16 * t_y
        max_playable_x = 0.72 + 0.16 * t_y

        if not (min_playable_x <= norm_x <= max_playable_x):
            return True

        return False

    def detect(
        self, frame: np.ndarray, use_frame_official_filter: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Detects active players in frame.
        Supports both 1v1 Singles (2 players) and 2v2 Doubles (up to 4 players).
        Strictly rejects all umpires, service judges, and line judges.
        Uses confidence gating to keep only the most confident detections.
        """
        h, w, _ = frame.shape
        if self.model is not None:
            # Higher resolution inference (640px) for better detection accuracy
            results = self._predict_with_fallback(frame)
            raw_detections = []
            for box in results.boxes if results is not None else []:
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
                if use_frame_official_filter and self.is_official_referee(
                    norm_x, norm_y_bottom, norm_y_top, norm_h, norm_w
                ):
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
                if not use_frame_official_filter:
                    return raw_detections

                # Sort by confidence descending, keep top detections to avoid ghost boxes
                raw_detections.sort(key=lambda d: d["confidence"], reverse=True)

                # Confidence gate: keep at most 4 detections (doubles max), usually 2 for singles
                raw_detections = raw_detections[:4]

                # Re-sort by y_bottom (ascending: far court players come first, near players last)
                raw_detections.sort(key=lambda d: d["bottom_center"][1])

                chosen = []
                if len(raw_detections) == 1:
                    # Single player detected
                    d = raw_detections[0]
                    d_copy = dict(d)
                    d_copy["role"] = "near" if d["bottom_center"][1] >= h * 0.62 else "far"
                    d_copy["rank"] = 1
                    chosen.append(d_copy)
                elif len(raw_detections) == 2:
                    # Standard Singles 1v1: Top one is Far Player, Bottom one is Near Player
                    far_p = dict(raw_detections[0])
                    far_p["role"] = "far"
                    far_p["rank"] = 1

                    near_p = dict(raw_detections[1])
                    near_p["role"] = "near"
                    near_p["rank"] = 1

                    chosen.extend([near_p, far_p])
                elif len(raw_detections) == 3:
                    # 3 players: identify whether 2 are far or 2 are near based on optical net line (y ~ 0.53)
                    far_cands = [d for d in raw_detections if d["bottom_center"][1] < h * 0.58]
                    near_cands = [d for d in raw_detections if d["bottom_center"][1] >= h * 0.58]

                    if len(far_cands) >= 2:
                        for j, fc in enumerate(far_cands[:2]):
                            fc_copy = dict(fc)
                            fc_copy["role"] = "far"
                            fc_copy["rank"] = j + 1
                            chosen.append(fc_copy)
                        if near_cands:
                            nc_copy = dict(near_cands[0])
                            nc_copy["role"] = "near"
                            nc_copy["rank"] = 1
                            chosen.append(nc_copy)
                    else:
                        if far_cands:
                            fc_copy = dict(far_cands[0])
                            fc_copy["role"] = "far"
                            fc_copy["rank"] = 1
                            chosen.append(fc_copy)
                        for i, nc in enumerate(near_cands[:2]):
                            nc_copy = dict(nc)
                            nc_copy["role"] = "near"
                            nc_copy["rank"] = i + 1
                            chosen.append(nc_copy)
                else:
                    # 4 or more players: Top 2 are Far Doubles, Bottom 2 are Near Doubles
                    for j, fc in enumerate(raw_detections[:2]):
                        fc_copy = dict(fc)
                        fc_copy["role"] = "far"
                        fc_copy["rank"] = j + 1
                        chosen.append(fc_copy)

                    for i, nc in enumerate(raw_detections[-2:]):
                        nc_copy = dict(nc)
                        nc_copy["role"] = "near"
                        nc_copy["rank"] = i + 1
                        chosen.append(nc_copy)

                if chosen:
                    return chosen

        if os.getenv("ENABLE_SYNTHETIC_DETECTIONS", "0") == "1":
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
        return []
