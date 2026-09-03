"""YOLO pose estimation associated with the court-filtered player detections."""

import os
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from ml.runtime.capabilities import get_runtime_capabilities
from ml.tracking.deep_eiou import expansion_iou


KEYPOINT_NAMES = (
    "nose",
    "left_eye",
    "right_eye",
    "left_ear",
    "right_ear",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
)

ANGLE_JOINTS = {
    "left_elbow": ("left_shoulder", "left_elbow", "left_wrist"),
    "right_elbow": ("right_shoulder", "right_elbow", "right_wrist"),
    "left_knee": ("left_hip", "left_knee", "left_ankle"),
    "right_knee": ("right_hip", "right_knee", "right_ankle"),
    "left_shoulder": ("left_elbow", "left_shoulder", "left_hip"),
    "right_shoulder": ("right_elbow", "right_shoulder", "right_hip"),
}


class AthletePoseEstimator:
    def __init__(self, model_path: str | None = None):
        workspace_root = Path(__file__).resolve().parents[2]
        self.model_path = model_path or os.getenv(
            "POSE_MODEL_PATH", str(workspace_root / "models" / "yolo11n-pose.pt")
        )
        self.enabled = os.getenv("ENABLE_POSE", "1") == "1"
        capabilities = get_runtime_capabilities()["components"]
        self.device = os.getenv(
            "POSE_DEVICE", "0" if capabilities["cuda"]["available"] else "cpu"
        )
        self.model = None

    def _load(self) -> bool:
        if not self.enabled:
            return False
        if self.model is not None:
            return True
        try:
            from ultralytics import YOLO

            self.model = YOLO(self.model_path)
            print(f"[Pose] Loaded athlete pose model: {self.model_path} ({self.device})")
            return True
        except Exception as exc:
            print(f"[Pose] Disabled after model load failure: {exc}")
            self.enabled = False
            return False

    @staticmethod
    def _joint_angle(
        keypoints: Dict[str, List[float]], first: str, middle: str, last: str
    ) -> float | None:
        points = [keypoints.get(name) for name in (first, middle, last)]
        if any(point is None or point[2] < 0.25 for point in points):
            return None
        a, b, c = (np.asarray(point[:2], dtype=np.float32) for point in points)
        first_vector = a - b
        second_vector = c - b
        denominator = float(np.linalg.norm(first_vector) * np.linalg.norm(second_vector))
        if denominator <= 1e-6:
            return None
        cosine = float(np.clip(np.dot(first_vector, second_vector) / denominator, -1.0, 1.0))
        return round(float(np.degrees(np.arccos(cosine))), 1)

    def enrich(
        self,
        frame: np.ndarray,
        detections: List[Dict[str, Any]],
        include_unmatched: bool = False,
    ) -> List[Dict[str, Any]]:
        if (not detections and not include_unmatched) or not self._load():
            return detections

        try:
            result = self.model.predict(
                source=frame,
                classes=[0],
                conf=float(os.getenv("POSE_CONFIDENCE", "0.15")),
                imgsz=int(os.getenv("POSE_IMAGE_SIZE", "960")),
                device=self.device,
                verbose=False,
            )[0]
            if result.keypoints is None or result.boxes is None:
                return detections
            pose_boxes = result.boxes.xyxy.detach().cpu().numpy()
            pose_data = result.keypoints.data.detach().cpu().numpy()
            pose_confidences = result.boxes.conf.detach().cpu().numpy()
        except Exception as exc:
            print(f"[Pose] Frame inference failed: {exc}")
            return detections

        enriched = [dict(detection) for detection in detections]
        unused = set(range(min(len(pose_boxes), len(pose_data))))

        def pose_payload(index: int) -> Dict[str, Any]:
            named_keypoints: Dict[str, List[float]] = {}
            for name, values in zip(KEYPOINT_NAMES, pose_data[index]):
                x, y, confidence = values[:3]
                named_keypoints[name] = [
                    round(float(x), 1),
                    round(float(y), 1),
                    round(float(confidence), 3),
                ]
            angles = {
                name: angle
                for name, joints in ANGLE_JOINTS.items()
                if (angle := self._joint_angle(named_keypoints, *joints)) is not None
            }
            return {
                "source": "ultralytics-yolo-pose",
                "keypoints": named_keypoints,
                "angles": angles,
            }

        for detection_index, detection in enumerate(detections):
            if not unused:
                break
            best_index = max(
                unused,
                key=lambda index: expansion_iou(
                    detection["bbox"], pose_boxes[index].astype(float).tolist()
                ),
            )
            overlap = expansion_iou(
                detection["bbox"], pose_boxes[best_index].astype(float).tolist()
            )
            if overlap < 0.12:
                continue
            unused.remove(best_index)
            enriched[detection_index]["pose"] = pose_payload(best_index)

        if include_unmatched:
            for index in unused:
                x1, y1, x2, y2 = pose_boxes[index].astype(float).tolist()
                confidence = float(pose_confidences[index])
                enriched.append(
                    {
                        "bbox": [round(value, 1) for value in (x1, y1, x2, y2)],
                        "bottom_center": [round((x1 + x2) / 2.0, 1), round(y2, 1)],
                        "confidence": round(confidence, 3),
                        "box_area": (x2 - x1) * (y2 - y1),
                        "box_h": y2 - y1,
                        "class": "player",
                        "pose": pose_payload(index),
                    }
                )
        return enriched
