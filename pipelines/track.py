"""
Unified Tracking Pipeline:
Coordinates player tracking and shuttle trajectory smoothing across video frames.
"""

from typing import List, Dict, Any, Optional
import numpy as np
from ml.tracking.tracker import PlayerTracker
from ml.tracking.shuttle_tracker import ShuttleTrajectoryTracker
from ml.tracking.racket_tracker import RacketTracker
from ml.reid.osnet import OSNetEmbedder
from ml.runtime.capabilities import get_runtime_capabilities


class TrackingPipeline:
    def __init__(self):
        self.player_tracker = PlayerTracker()
        self.shuttle_tracker = ShuttleTrajectoryTracker()
        self.racket_tracker = RacketTracker()
        cuda_available = get_runtime_capabilities()["components"]["cuda"]["available"]
        self.reid_embedder = OSNetEmbedder(device="0" if cuda_available else "cpu")

    def update(
        self,
        detections: Dict[str, Any],
        frame_idx: int,
        timestamp: float,
        frame: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """
        Updates trackers with raw detections for a given frame.
        """
        player_dets = detections.get("players", [])
        shuttle_det = detections.get("shuttle")
        racket_dets = detections.get("rackets", [])

        if frame is not None:
            player_dets = self.reid_embedder.attach_embeddings(frame, player_dets)

        tracked_players = self.player_tracker.update(player_dets, frame_idx)
        tracked_rackets = self.racket_tracker.update(racket_dets, tracked_players, frame_idx)
        frame_shape = frame.shape[:2] if frame is not None else None
        tracked_shuttle = self.shuttle_tracker.update(
            shuttle_det, frame_idx, timestamp, frame_shape=frame_shape
        )

        return {
            "players": tracked_players,
            "rackets": tracked_rackets,
            "shuttle": tracked_shuttle,
        }
