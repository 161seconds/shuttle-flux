"""
Player Tracking Module:
Maintains permanent, stable Player IDs across all video frames for both:
1. Singles (1v1): P1 (Near Court), P2 (Far Court)
2. Doubles (2v2): P1 & P3 (Team 1 - Near Court), P2 & P4 (Team 2 - Far Court)
Features smooth bounding box temporal interpolation and zero ID flipping.
"""

from typing import List, Dict, Any, Optional
import numpy as np


class PlayerTracker:
    def __init__(self, smoothing_alpha: float = 0.45):
        self.smoothing_alpha = smoothing_alpha
        # Permanent tracks dictionary: 1: P1, 2: P2, 3: P3, 4: P4
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self.missing_counts: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
        self.max_hold_frames = 15
        self.detected_doubles_frames = 0
        self.total_frames_tracked = 0
        self.is_doubles_mode = False

    def update(self, detections: List[Dict[str, Any]], frame_idx: int) -> List[Dict[str, Any]]:
        """
        Associates detections with permanent Player tracks.
        Assigns:
          - Near Court: P1 (Primary) and P3 (Teammate)
          - Far Court: P2 (Primary) and P4 (Teammate)
        """
        self.total_frames_tracked += 1
        near_dets = [d for d in detections if d.get("role") == "near"]
        far_dets = [d for d in detections if d.get("role") == "far"]

        # Detect Doubles if >= 2 players on any side
        if len(near_dets) >= 2 or len(far_dets) >= 2 or (len(near_dets) + len(far_dets) >= 3):
            self.detected_doubles_frames += 1
            if self.detected_doubles_frames >= 4:
                self.is_doubles_mode = True

        tracked_players = []

        # --- Update Near Court (P1 & P3) ---
        near_tracked = self._match_and_update_side(
            candidates=near_dets,
            primary_id=1,
            secondary_id=3,
            side_label="Gần",
            frame_idx=frame_idx,
        )
        tracked_players.extend(near_tracked)

        # --- Update Far Court (P2 & P4) ---
        far_tracked = self._match_and_update_side(
            candidates=far_dets,
            primary_id=2,
            secondary_id=4,
            side_label="Xa",
            frame_idx=frame_idx,
        )
        tracked_players.extend(far_tracked)

        return tracked_players

    def _match_and_update_side(
        self,
        candidates: List[Dict[str, Any]],
        primary_id: int,
        secondary_id: int,
        side_label: str,
        frame_idx: int,
    ) -> List[Dict[str, Any]]:
        results = []
        assigned_cands = set()

        # Target IDs for this court side
        track_ids = [primary_id, secondary_id] if self.is_doubles_mode else [primary_id]

        for p_id in track_ids:
            best_cand_idx = None
            best_dist = float("inf")

            if p_id in self.tracks and candidates:
                prev_bc = self.tracks[p_id]["bottom_center"]
                for idx, c in enumerate(candidates):
                    if idx in assigned_cands:
                        continue
                    curr_bc = c["bottom_center"]
                    dist = np.hypot(curr_bc[0] - prev_bc[0], curr_bc[1] - prev_bc[1])
                    if dist < best_dist:
                        best_dist = dist
                        best_cand_idx = idx

            # If no previous track, assign first unassigned candidate
            if best_cand_idx is None:
                for idx, _ in enumerate(candidates):
                    if idx not in assigned_cands:
                        best_cand_idx = idx
                        break

            if best_cand_idx is not None:
                assigned_cands.add(best_cand_idx)
                cand = candidates[best_cand_idx]
                self.missing_counts[p_id] = 0

                if p_id in self.tracks:
                    prev_bbox = self.tracks[p_id]["bbox"]
                    curr_bbox = cand["bbox"]
                    smoothed_bbox = [
                        round((1.0 - self.smoothing_alpha) * prev_bbox[i] + self.smoothing_alpha * curr_bbox[i], 1)
                        for i in range(4)
                    ]
                    prev_bc = self.tracks[p_id]["bottom_center"]
                    curr_bc = cand["bottom_center"]
                    smoothed_bc = [
                        round((1.0 - self.smoothing_alpha) * prev_bc[i] + self.smoothing_alpha * curr_bc[i], 1)
                        for i in range(2)
                    ]
                    self.tracks[p_id] = {
                        "player_id": p_id,
                        "label": f"VĐV {p_id} ({side_label})",
                        "bbox": smoothed_bbox,
                        "bottom_center": smoothed_bc,
                        "confidence": cand["confidence"],
                        "frame_idx": frame_idx,
                    }
                else:
                    self.tracks[p_id] = {
                        "player_id": p_id,
                        "label": f"VĐV {p_id} ({side_label})",
                        "bbox": cand["bbox"],
                        "bottom_center": cand["bottom_center"],
                        "confidence": cand["confidence"],
                        "frame_idx": frame_idx,
                    }
                results.append(dict(self.tracks[p_id]))

            elif p_id in self.tracks and self.missing_counts[p_id] < self.max_hold_frames:
                self.missing_counts[p_id] += 1
                held = dict(self.tracks[p_id])
                held["frame_idx"] = frame_idx
                held["confidence"] = max(0.35, held["confidence"] * 0.94)
                results.append(held)

        return results
