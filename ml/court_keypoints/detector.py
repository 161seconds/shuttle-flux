"""
Court Keypoint Detector:
Identifies 4 to 14 court keypoints on the image for homography calibration.
"""

from typing import Dict, List, Tuple, Optional
import numpy as np


class CourtKeypointDetector:
    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.model = None

    def detect_keypoints(self, frame: np.ndarray) -> Dict[str, Tuple[float, float]]:
        """
        Detects primary court corners in image pixels.
        Returns mapping of corner names to (px_x, px_y).
        """
        h, w, _ = frame.shape
        # Standard camera angle heuristic default (approx. trapezoid court in view)
        return {
            "corner_bottom_left": (w * 0.15, h * 0.90),
            "corner_bottom_right": (w * 0.85, h * 0.90),
            "corner_top_left": (w * 0.35, h * 0.20),
            "corner_top_right": (w * 0.65, h * 0.20),
            "net_left": (w * 0.25, h * 0.55),
            "net_right": (w * 0.75, h * 0.55),
        }
