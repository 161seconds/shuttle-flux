"""SAM 3 mask refinement for YOLO player detections."""

import os
from pathlib import Path
from typing import Any, Dict, List

import cv2
import numpy as np


class SAM3PlayerRefiner:
    def __init__(self, model_path: str | None = None, device: str = "cpu"):
        workspace_root = Path(__file__).resolve().parents[2]
        self.model_path = Path(
            model_path
            or os.getenv("SAM3_MODEL_PATH", workspace_root / "models" / "sam3.pt")
        )
        self.device = device
        self.enabled = os.getenv("ENABLE_SAM3", "0") == "1" and self.model_path.is_file()
        self.model = None

    def _load(self) -> bool:
        if not self.enabled:
            return False
        if self.model is not None:
            return True
        try:
            from ultralytics import SAM

            self.model = SAM(str(self.model_path))
            print(f"[SAM3] Loaded promptable segmentation model: {self.model_path}")
            return True
        except Exception as exc:
            print(f"[SAM3] Disabled after model load failure: {exc}")
            self.enabled = False
            return False

    def refine(
        self, frame: np.ndarray, detections: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not detections or not self._load():
            return detections

        boxes = [detection["bbox"] for detection in detections]
        try:
            results = self.model.predict(
                source=frame,
                bboxes=boxes,
                device=self.device,
                verbose=False,
            )
            if not results or results[0].masks is None:
                return detections
            masks = results[0].masks.data.detach().cpu().numpy()
        except Exception as exc:
            print(f"[SAM3] Frame refinement failed: {exc}")
            return detections

        refined = [dict(detection) for detection in detections]
        frame_h, frame_w = frame.shape[:2]
        for index, mask in enumerate(masks[: len(refined)]):
            if mask.shape != (frame_h, frame_w):
                mask = cv2.resize(mask, (frame_w, frame_h), interpolation=cv2.INTER_NEAREST)
            ys, xs = np.where(mask > 0.5)
            if len(xs) == 0:
                continue

            bottom_y = int(ys.max())
            bottom_band = xs[ys >= max(0, bottom_y - 3)]
            bottom_x = float(np.median(bottom_band)) if len(bottom_band) else float(np.median(xs))
            bbox = refined[index]["bbox"]
            bbox_area = max(1.0, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
            refined[index]["bottom_center"] = [round(bottom_x, 1), round(float(bottom_y), 1)]
            refined[index]["mask_area_ratio"] = round(float(len(xs) / bbox_area), 3)
            refined[index]["segmentation_source"] = "sam3"

        return refined
