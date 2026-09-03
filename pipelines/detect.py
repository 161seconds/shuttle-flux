"""
Unified Detection Pipeline:
Orchestrates player detection, shuttlecock detection, and court keypoint models on a single frame.
"""

import os
from typing import Dict, Any, Callable, List, Optional
import numpy as np
import cv2
from ml.player_detection.detector import PlayerDetector
from ml.shuttle_detection.detector import ShuttleDetector
from ml.court_keypoints.detector import CourtKeypointDetector
from ml.equipment.racket import RacketDetector
from ml.pose.athlete_pose import AthletePoseEstimator
from ml.segmentation.sam3 import SAM3PlayerRefiner


class DetectionPipeline:
    def __init__(
        self,
        player_model_path: Optional[str] = None,
        shuttle_model_path: Optional[str] = None,
        court_model_path: Optional[str] = None,
        service_url: Optional[str] = None,
        use_remote: bool = True,
    ):
        self.player_model_path = player_model_path
        self.shuttle_model_path = shuttle_model_path
        self.service_url = (
            service_url if service_url is not None else os.getenv("INFERENCE_SERVICE_URL", "")
        ).rstrip("/")
        self.use_remote = use_remote and bool(self.service_url)
        self.http_session = None
        self.player_detector = None
        self.shuttle_detector = None
        self.court_detector = CourtKeypointDetector(court_model_path)
        self.sam3_refiner = None
        self.pose_estimator = None
        self.racket_detector = None
        self.frame_count = 0
        self.sam3_interval = max(1, int(os.getenv("SAM3_FRAME_INTERVAL", "10")))
        self.pose_interval = max(1, int(os.getenv("POSE_FRAME_INTERVAL", "2")))
        self.racket_interval = max(1, int(os.getenv("RACKET_FRAME_INTERVAL", "2")))
        if not self.use_remote:
            self._ensure_local_models()

    def _ensure_local_models(self) -> None:
        if self.player_detector is None:
            self.player_detector = PlayerDetector(self.player_model_path)
        if self.shuttle_detector is None:
            self.shuttle_detector = ShuttleDetector(self.shuttle_model_path)
        if self.sam3_refiner is None:
            self.sam3_refiner = SAM3PlayerRefiner(device=self.player_detector.device)
        if self.pose_estimator is None:
            self.pose_estimator = AthletePoseEstimator()
        if self.racket_detector is None:
            self.racket_detector = RacketDetector(
                shared_model=self.player_detector.model,
                device=self.player_detector.device,
            )

    def _run_remote(self, frame: np.ndarray) -> Dict[str, Any]:
        import requests

        if self.http_session is None:
            self.http_session = requests.Session()
        jpeg_quality = int(os.getenv("INFERENCE_JPEG_QUALITY", "88"))
        encoded, buffer = cv2.imencode(
            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]
        )
        if not encoded:
            raise ValueError("Could not encode frame for remote inference")
        response = self.http_session.post(
            f"{self.service_url}/v1/detect",
            files={"image": ("frame.jpg", buffer.tobytes(), "image/jpeg")},
            timeout=float(os.getenv("INFERENCE_SERVICE_TIMEOUT_SEC", "30")),
        )
        response.raise_for_status()
        payload = response.json()
        return {
            "players": payload.get("players", []),
            "rackets": payload.get("rackets", []),
            "shuttle": payload.get("shuttle"),
            "runtime": payload.get("runtime", {}),
        }

    def detect_court(self, frame: np.ndarray) -> Dict[str, Any]:
        """Detects keypoints of the court."""
        return self.court_detector.detect_keypoints(frame)

    def run_frame(
        self,
        frame: np.ndarray,
        player_filter: Optional[Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """Runs player and shuttle detection on frame."""
        self.frame_count += 1
        if self.use_remote:
            try:
                result = self._run_remote(frame)
                if player_filter is not None:
                    result["players"] = player_filter(result["players"])
                return result
            except Exception as exc:
                print(f"[DetectionPipeline] Remote inference failed, using local fallback: {exc}")
                self.use_remote = False

        self._ensure_local_models()
        players = self.player_detector.detect(
            frame, use_frame_official_filter=player_filter is None
        )
        if player_filter is not None:
            players = player_filter(players)
        if self.frame_count % self.sam3_interval == 0:
            players = self.sam3_refiner.refine(frame, players)
        if self.frame_count % self.pose_interval == 0:
            players = self.pose_estimator.enrich(
                frame,
                players,
                include_unmatched=player_filter is not None,
            )
            if player_filter is not None:
                players = player_filter(players)

        rackets = []
        if self.frame_count % self.racket_interval == 0:
            self.racket_detector.shared_model = self.player_detector.model
            self.racket_detector.device = self.player_detector.device
            rackets = self.racket_detector.detect(frame)
        player_boxes = [p["bbox"] for p in players if "bbox" in p]
        shuttle = self.shuttle_detector.detect(frame, player_boxes=player_boxes)

        return {
            "players": players,
            "rackets": rackets,
            "shuttle": shuttle,
            "runtime": self.player_detector.get_runtime_info(),
        }
