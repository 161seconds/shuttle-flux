"""
Rally Segmentation & State Machine:
Detects rally start, active exchanges, and rally end events from video tracking data.
"""

from enum import Enum
from typing import List, Dict, Any, Optional


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
        self.min_rally_duration_sec = min_rally_duration_sec
        self.max_shuttle_lost_sec = max_shuttle_lost_sec
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
        last_active_idx: Optional[int] = None
        last_active_time: Optional[float] = None
        rally_counter = 1

        def append_rally(start_idx: int, end_idx: int, confidence: float) -> None:
            nonlocal rally_counter
            start_time = float(frames_data[start_idx].get("timestamp", start_idx / self.fps))
            end_time = float(frames_data[end_idx].get("timestamp", end_idx / self.fps))
            duration_sec = max(0.0, end_time - start_time)
            if duration_sec < self.min_rally_duration_sec:
                return

            rallies.append(
                {
                    "rally_id": rally_counter,
                    "name": f"Rally #{rally_counter}",
                    "start_frame": frames_data[start_idx]["frame_idx"],
                    "end_frame": frames_data[end_idx]["frame_idx"],
                    "start_time": round(start_time, 2),
                    "end_time": round(end_time, 2),
                    "duration_seconds": round(duration_sec, 2),
                    "estimated_shot_count": max(2, int(duration_sec * 1.2)),
                    "confidence": confidence,
                }
            )
            rally_counter += 1

        for i, f in enumerate(frames_data):
            shuttle = f.get("shuttle")
            is_shuttle_active = False
            timestamp = float(f.get("timestamp", i / self.fps))

            if shuttle and shuttle.get("visible", False):
                speed = shuttle.get("speed_norm")
                # Older/partial producers may not provide speed; visibility is then
                # the best available rally signal.
                if speed is None or float(speed) >= self.min_shuttle_speed:
                    is_shuttle_active = True

            if current_state == RallyState.IDLE:
                if is_shuttle_active:
                    current_state = RallyState.ACTIVE
                    rally_start_idx = i
                    last_active_idx = i
                    last_active_time = timestamp

            elif current_state == RallyState.ACTIVE:
                if is_shuttle_active:
                    last_active_idx = i
                    last_active_time = timestamp
                elif (
                    last_active_idx is not None
                    and last_active_time is not None
                    and timestamp - last_active_time > self.max_shuttle_lost_sec
                ):
                    append_rally(rally_start_idx, last_active_idx, 0.88)
                    current_state = RallyState.IDLE
                    last_active_idx = None
                    last_active_time = None

        # Check trailing active rally at end of video
        if current_state == RallyState.ACTIVE and last_active_idx is not None:
            append_rally(rally_start_idx, last_active_idx, 0.85)

        return rallies
