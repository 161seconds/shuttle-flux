"""
Player Tracking Module:
Maintains permanent, stable Player IDs (P1 = Near Court, P2 = Far Court) across all video frames
with smooth bounding box temporal interpolation and zero ID flipping.
"""

from typing import List, Dict, Any, Optional


class PlayerTracker:
    def __init__(self, smoothing_alpha: float = 0.45):
        self.smoothing_alpha = smoothing_alpha
        # Permanent tracks for P1 (Near Court) and P2 (Far Court)
        self.p1_track: Optional[Dict[str, Any]] = None
        self.p2_track: Optional[Dict[str, Any]] = None
        self.p1_missing = 0
        self.p2_missing = 0
        self.max_hold_frames = 15

    def update(self, detections: List[Dict[str, Any]], frame_idx: int) -> List[Dict[str, Any]]:
        """
        Associates detections with permanent P1 and P2 tracks.
        P1 is strictly locked to Near Court (lower half), P2 to Far Court (upper half).
        """
        near_det = None
        far_det = None

        for d in detections:
            role = d.get("role")
            if role == "near":
                if near_det is None or d["confidence"] > near_det["confidence"]:
                    near_det = d
            elif role == "far":
                if far_det is None or d["confidence"] > far_det["confidence"]:
                    far_det = d

        # Safety check: ensure near_det and far_det are distinctly separated in Y
        if near_det is not None and far_det is not None:
            if abs(near_det["bottom_center"][1] - far_det["bottom_center"][1]) < 30:
                # If they overlap, keep only the higher confidence one
                if near_det["confidence"] >= far_det["confidence"]:
                    far_det = None
                else:
                    near_det = None

        tracked_players = []

        # --- Update P1 (Near Player - Cyan) ---
        if near_det is not None:
            self.p1_missing = 0
            if self.p1_track is not None:
                # Smooth bbox interpolation
                prev_bbox = self.p1_track["bbox"]
                curr_bbox = near_det["bbox"]
                smoothed_bbox = [
                    round((1.0 - self.smoothing_alpha) * prev_bbox[i] + self.smoothing_alpha * curr_bbox[i], 1)
                    for i in range(4)
                ]
                prev_bc = self.p1_track["bottom_center"]
                curr_bc = near_det["bottom_center"]
                smoothed_bc = [
                    round((1.0 - self.smoothing_alpha) * prev_bc[i] + self.smoothing_alpha * curr_bc[i], 1)
                    for i in range(2)
                ]
                self.p1_track = {
                    "player_id": 1,
                    "label": "VĐV 1 (Gần)",
                    "bbox": smoothed_bbox,
                    "bottom_center": smoothed_bc,
                    "confidence": near_det["confidence"],
                    "frame_idx": frame_idx,
                }
            else:
                self.p1_track = {
                    "player_id": 1,
                    "label": "VĐV 1 (Gần)",
                    "bbox": near_det["bbox"],
                    "bottom_center": near_det["bottom_center"],
                    "confidence": near_det["confidence"],
                    "frame_idx": frame_idx,
                }
            tracked_players.append(dict(self.p1_track))
        elif self.p1_track is not None and self.p1_missing < self.max_hold_frames:
            self.p1_missing += 1
            held_p1 = dict(self.p1_track)
            held_p1["frame_idx"] = frame_idx
            held_p1["confidence"] = max(0.4, held_p1["confidence"] * 0.95)
            tracked_players.append(held_p1)

        # --- Update P2 (Far Player - Amber) ---
        if far_det is not None:
            self.p2_missing = 0
            if self.p2_track is not None:
                # Smooth bbox interpolation
                prev_bbox = self.p2_track["bbox"]
                curr_bbox = far_det["bbox"]
                smoothed_bbox = [
                    round((1.0 - self.smoothing_alpha) * prev_bbox[i] + self.smoothing_alpha * curr_bbox[i], 1)
                    for i in range(4)
                ]
                prev_bc = self.p2_track["bottom_center"]
                curr_bc = far_det["bottom_center"]
                smoothed_bc = [
                    round((1.0 - self.smoothing_alpha) * prev_bc[i] + self.smoothing_alpha * curr_bc[i], 1)
                    for i in range(2)
                ]
                self.p2_track = {
                    "player_id": 2,
                    "label": "VĐV 2 (Xa)",
                    "bbox": smoothed_bbox,
                    "bottom_center": smoothed_bc,
                    "confidence": far_det["confidence"],
                    "frame_idx": frame_idx,
                }
            else:
                self.p2_track = {
                    "player_id": 2,
                    "label": "VĐV 2 (Xa)",
                    "bbox": far_det["bbox"],
                    "bottom_center": far_det["bottom_center"],
                    "confidence": far_det["confidence"],
                    "frame_idx": frame_idx,
                }
            tracked_players.append(dict(self.p2_track))
        elif self.p2_track is not None and self.p2_missing < self.max_hold_frames:
            self.p2_missing += 1
            held_p2 = dict(self.p2_track)
            held_p2["frame_idx"] = frame_idx
            held_p2["confidence"] = max(0.4, held_p2["confidence"] * 0.95)
            tracked_players.append(held_p2)

        return tracked_players
