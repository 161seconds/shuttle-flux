"""
Unified Tracking Pipeline:
Coordinates player tracking and shuttle trajectory smoothing across video frames.
"""

from typing import List, Dict, Any, Optional
from ml.tracking.tracker import PlayerTracker
from ml.tracking.shuttle_tracker import ShuttleTrajectoryTracker


class TrackingPipeline:
    def __init__(self):
        self.player_tracker = PlayerTracker()
        self.shuttle_tracker = ShuttleTrajectoryTracker()

    def update(
        self,
        detections: Dict[str, Any],
        frame_idx: int,
        timestamp: float,
    ) -> Dict[str, Any]:
        """
        Updates trackers with raw detections for a given frame.
        """
        player_dets = detections.get("players", [])
        shuttle_det = detections.get("shuttle")

        tracked_players = self.player_tracker.update(player_dets, frame_idx)
        tracked_shuttle = self.shuttle_tracker.update(shuttle_det, frame_idx, timestamp)

        return {
            "players": tracked_players,
            "shuttle": tracked_shuttle,
        }
