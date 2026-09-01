"""
Shuttlecock Tracking & Trajectory Smoothing Module:
Maintains smooth, aerodynamic flight trajectories for badminton shuttlecocks.
Implements:
1. Physical jump-distance outlier rejection (ignores false positive teleportations)
2. Exponential Moving Average (EMA) coordinate dampening (eliminates micro-jitter)
3. Smooth ballistic velocity extrapolation during fast motion blur / occlusions.
"""

from typing import Dict, Any, Optional, List
import numpy as np


class ShuttleTrajectoryTracker:
    def __init__(self, max_missing_frames: int = 6, smoothing_alpha: float = 0.42):
        self.max_missing_frames = max_missing_frames
        self.smoothing_alpha = smoothing_alpha
        self.state = "LOST"
        self.missing_count = 0
        self.trajectory_history: List[Dict[str, Any]] = []
        
        # Velocity estimation (dx, dy) per frame
        self.last_valid_pos: Optional[List[float]] = None
        self.velocity: List[float] = [0.0, 0.0]

    def update(
        self,
        detection: Optional[Dict[str, Any]],
        frame_idx: int,
        timestamp: float,
    ) -> Dict[str, Any]:
        """
        Updates shuttle trajectory with physical velocity gating and EMA smoothing.
        """
        raw_valid = detection is not None and detection.get("visible", False) and "center" in detection

        if raw_valid:
            curr_center = detection["center"]
            cx, cy = float(curr_center[0]), float(curr_center[1])

            # 1. Physical Jump-Distance Gate: Reject sudden teleportations across the screen
            if self.last_valid_pos is not None and self.missing_count <= 3:
                prev_cx, prev_cy = self.last_valid_pos
                dist_jump = np.hypot(cx - prev_cx, cy - prev_cy)
                
                # If jump exceeds 220 pixels in 1 frame (~20% of 1080p), check if it's an outlier
                if dist_jump > 220:
                    # Treat as outlier noise artifact; extrapolate instead of jumping
                    return self._handle_missing_extrapolation(frame_idx, timestamp)

            # 2. Smooth Position via Exponential Moving Average (EMA)
            if self.last_valid_pos is not None and self.missing_count == 0:
                smoothed_cx = (1.0 - self.smoothing_alpha) * self.last_valid_pos[0] + self.smoothing_alpha * cx
                smoothed_cy = (1.0 - self.smoothing_alpha) * self.last_valid_pos[1] + self.smoothing_alpha * cy
                
                # Update velocity estimate with slight damping
                self.velocity = [
                    (smoothed_cx - self.last_valid_pos[0]),
                    (smoothed_cy - self.last_valid_pos[1]),
                ]
                self.last_valid_pos = [smoothed_cx, smoothed_cy]
            else:
                self.last_valid_pos = [cx, cy]
                self.velocity = [0.0, 0.0]

            self.state = "DETECTED"
            self.missing_count = 0

            curr_point = dict(detection)
            curr_point["frame_idx"] = frame_idx
            curr_point["timestamp"] = timestamp
            curr_point["center"] = [round(self.last_valid_pos[0], 1), round(self.last_valid_pos[1], 1)]
            curr_point["visible"] = True
            curr_point["confidence"] = detection.get("confidence", 0.90)

            self.trajectory_history.append(curr_point)
            return curr_point

        else:
            return self._handle_missing_extrapolation(frame_idx, timestamp)

    def _handle_missing_extrapolation(self, frame_idx: int, timestamp: float) -> Dict[str, Any]:
        self.missing_count += 1
        
        # Extrapolate smoothly for up to 3 frames with aerodynamic air drag
        if self.missing_count <= 3 and self.last_valid_pos is not None:
            self.state = "TEMPORARILY_MISSING"
            drag = 0.82 ** self.missing_count
            extrap_cx = self.last_valid_pos[0] + self.velocity[0] * drag
            extrap_cy = self.last_valid_pos[1] + self.velocity[1] * drag
            self.last_valid_pos = [extrap_cx, extrap_cy]

            last_rec = self.trajectory_history[-1] if self.trajectory_history else {}
            interpolated = dict(last_rec)
            interpolated["frame_idx"] = frame_idx
            interpolated["timestamp"] = timestamp
            interpolated["center"] = [round(extrap_cx, 1), round(extrap_cy, 1)]
            interpolated["visible"] = True
            interpolated["confidence"] = max(0.3, last_rec.get("confidence", 0.8) * 0.75)
            
            self.trajectory_history.append(interpolated)
            return interpolated
        else:
            self.state = "LOST"
            self.last_valid_pos = None
            self.velocity = [0.0, 0.0]
            
            point = {
                "frame_idx": frame_idx,
                "timestamp": timestamp,
                "visible": False,
                "confidence": 0.0,
            }
            self.trajectory_history.append(point)
            return point
