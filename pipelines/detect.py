"""
Unified Detection Pipeline:
Orchestrates player detection, shuttlecock detection, and court keypoint models on a single frame.
"""

from typing import Dict, Any, Optional
import numpy as np
from ml.player_detection.detector import PlayerDetector
from ml.shuttle_detection.detector import ShuttleDetector
from ml.court_keypoints.detector import CourtKeypointDetector


class DetectionPipeline:
    def __init__(
        self,
        player_model_path: Optional[str] = None,
        shuttle_model_path: Optional[str] = None,
        court_model_path: Optional[str] = None,
    ):
        self.player_detector = PlayerDetector(player_model_path)
        self.shuttle_detector = ShuttleDetector(shuttle_model_path)
        self.court_detector = CourtKeypointDetector(court_model_path)

    def detect_court(self, frame: np.ndarray) -> Dict[str, Any]:
        """Detects keypoints of the court."""
        return self.court_detector.detect_keypoints(frame)

    def run_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """Runs player and shuttle detection on frame."""
        players = self.player_detector.detect(frame)
        shuttle = self.shuttle_detector.detect(frame)

        return {
            "players": players,
            "shuttle": shuttle,
        }
