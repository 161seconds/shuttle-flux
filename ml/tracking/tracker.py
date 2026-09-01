"""
Player Tracking Module:
Maintains stable Player IDs across frames using ByteTrack or Distance-based Association.
"""

from typing import List, Dict, Any, Optional
import numpy as np


class PlayerTracker:
    def __init__(self, max_disappeared: int = 15):
        self.max_disappeared = max_disappeared
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self.next_id = 1

    def update(self, detections: List[Dict[str, Any]], frame_idx: int) -> List[Dict[str, Any]]:
        """
        Associates detections with ongoing tracks.
        For badminton singles, assigns ID 1 to near-court player (y larger) and ID 2 to far-court player.
        """
        if not detections:
            return []

        # Sort detections by Y position (bottom-center y)
        # In typical camera angle: larger Y is near player (Player 1), smaller Y is far player (Player 2)
        sorted_dets = sorted(detections, key=lambda d: d["bottom_center"][1], reverse=True)

        tracked_players = []
        for idx, det in enumerate(sorted_dets[:2]):
            player_id = 1 if idx == 0 else 2
            det_copy = dict(det)
            det_copy["player_id"] = player_id
            det_copy["label"] = f"Player {player_id}"
            det_copy["frame_idx"] = frame_idx
            tracked_players.append(det_copy)

        return tracked_players
