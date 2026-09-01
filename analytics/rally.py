"""
Rally Segmentation & State Machine:
Detects rally start, active exchanges, and rally end events from video tracking data.
"""

from enum import Enum
from typing import List, Dict, Any, Optional
import numpy as np


class RallyState(str, Enum):
    IDLE = "idle"
    RALLY_START = "rally_start"
    ACTIVE = "active"
    RALLY_END = "rally_end"


class RallySegmenter:
    """
    State machine for temporal rally segmentation.
    Uses shuttlecock visibility, speed, and player dynamics to segment match into rallies.
    """

    def __init__(
        self,
        fps: float = 30.0,
        min_rally_duration_sec: float = 2.0,
        max_shuttle_lost_sec: float = 0.8,
        min_shuttle_speed_norm: float = 0.05,
    ):
        self.fps = fps
        self.min_rally_frames = int(min_rally_duration_sec * fps)
        self.max_lost_frames = int(max_shuttle_lost_sec * fps)
        self.min_shuttle_speed = min_shuttle_speed_norm

    def segment(self, frames_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Processes sequential frame metadata to identify all rallies.
        Each frame_data contains:
          - frame_idx: int
          - timestamp: float (seconds)
          - shuttle: Optional[Dict] with 'x_norm', 'y_norm', 'visible', 'speed'
          - players: List[Dict] with 'id', 'x_norm', 'y_norm'
        """
        if not frames_data:
            return []

        rallies: List[Dict[str, Any]] = []
        current_state = RallyState.IDLE
        rally_start_idx = 0
        consecutive_lost = 0
        rally_counter = 1

        for i, f in enumerate(frames_data):
            shuttle = f.get("shuttle")
            is_shuttle_active = False

            if shuttle and shuttle.get("visible", False):
                speed = shuttle.get("speed_norm", 0.0)
                if speed >= self.min_shuttle_speed:
                    is_shuttle_active = True
                consecutive_lost = 0
            else:
                consecutive_lost += 1

            if current_state == RallyState.IDLE:
                if is_shuttle_active:
                    current_state = RallyState.ACTIVE
                    rally_start_idx = i
                    consecutive_lost = 0

            elif current_state == RallyState.ACTIVE:
                # If shuttle is lost for more than allowed dead-time, conclude rally
                if consecutive_lost > self.max_lost_frames:
                    rally_end_idx = i - consecutive_lost
                    duration_frames = rally_end_idx - rally_start_idx

                    if duration_frames >= self.min_rally_frames:
                        start_time = frames_data[rally_start_idx]["timestamp"]
                        end_time = frames_data[rally_end_idx]["timestamp"]
                        duration_sec = round(end_time - start_time, 2)

                        rallies.append(
                            {
                                "rally_id": rally_counter,
                                "name": f"Rally #{rally_counter}",
                                "start_frame": frames_data[rally_start_idx]["frame_idx"],
                                "end_frame": frames_data[rally_end_idx]["frame_idx"],
                                "start_time": round(start_time, 2),
                                "end_time": round(end_time, 2),
                                "duration_seconds": duration_sec,
                                "estimated_shot_count": max(2, int(duration_sec * 1.2)),
                                "confidence": 0.88,
                            }
                        )
                        rally_counter += 1

                    current_state = RallyState.IDLE
                    consecutive_lost = 0

        # Check trailing active rally at end of video
        if current_state == RallyState.ACTIVE:
            rally_end_idx = len(frames_data) - 1
            duration_frames = rally_end_idx - rally_start_idx
            if duration_frames >= self.min_rally_frames:
                start_time = frames_data[rally_start_idx]["timestamp"]
                end_time = frames_data[rally_end_idx]["timestamp"]
                rallies.append(
                    {
                        "rally_id": rally_counter,
                        "name": f"Rally #{rally_counter}",
                        "start_frame": frames_data[rally_start_idx]["frame_idx"],
                        "end_frame": frames_data[rally_end_idx]["frame_idx"],
                        "start_time": round(start_time, 2),
                        "end_time": round(end_time, 2),
                        "duration_seconds": round(end_time - start_time, 2),
                        "estimated_shot_count": max(2, int((end_time - start_time) * 1.2)),
                        "confidence": 0.85,
                    }
                )

        return rallies
