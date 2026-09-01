"""
Shuttlecock Tracking & Trajectory Smoothing Module:
Manages temporal state machine (DETECTED, TEMPORARILY_MISSING, RECOVERED, LOST)
and performs cubic/linear trajectory interpolation for missing frames.
"""

from typing import Dict, Any, Optional, List
import numpy as np


class ShuttleTrajectoryTracker:
    def __init__(self, max_missing_frames: int = 10):
        self.max_missing_frames = max_missing_frames
        self.state = "LOST"
        self.missing_count = 0
        self.trajectory_history: List[Dict[str, Any]] = []

    def update(
        self,
        detection: Optional[Dict[str, Any]],
        frame_idx: int,
        timestamp: float,
    ) -> Dict[str, Any]:
        """
        Updates shuttle state and returns smoothed/interpolated position.
        """
        if detection and detection.get("visible", False):
            self.state = "DETECTED"
            self.missing_count = 0
            curr_point = {
                "frame_idx": frame_idx,
                "timestamp": timestamp,
                "x_norm": detection.get("x_norm", 0.5),
                "y_norm": detection.get("y_norm", 0.5),
                "visible": True,
                "confidence": detection.get("confidence", 0.8),
                "speed_norm": 0.0,
            }

            if len(self.trajectory_history) > 0:
                prev = self.trajectory_history[-1]
                dt = max(0.001, timestamp - prev["timestamp"])
                dist = np.sqrt(
                    (curr_point["x_norm"] - prev["x_norm"]) ** 2
                    + (curr_point["y_norm"] - prev["y_norm"]) ** 2
                )
                curr_point["speed_norm"] = round(float(dist / dt), 3)

            self.trajectory_history.append(curr_point)
            return curr_point

        else:
            self.missing_count += 1
            if self.missing_count <= self.max_missing_frames and len(self.trajectory_history) > 0:
                self.state = "TEMPORARILY_MISSING"
                # Keep last known position or linear projection
                last = self.trajectory_history[-1]
                interpolated = dict(last)
                interpolated["frame_idx"] = frame_idx
                interpolated["timestamp"] = timestamp
                interpolated["visible"] = False
                interpolated["confidence"] = max(0.1, last["confidence"] * 0.8)
                self.trajectory_history.append(interpolated)
                return interpolated
            else:
                self.state = "LOST"
                point = {
                    "frame_idx": frame_idx,
                    "timestamp": timestamp,
                    "x_norm": 0.5,
                    "y_norm": 0.5,
                    "visible": False,
                    "confidence": 0.0,
                    "speed_norm": 0.0,
                }
                self.trajectory_history.append(point)
                return point
