"""
Player Tracking Module:
Maintains permanent, stable Player IDs across video frames with ZERO track duplication or ghost overlays.
Strictly adapts to the actual number of players on court:
  - 1v1 Singles: Exactly 2 players (P1 = Near, P2 = Far). No phantom P3/P4.
  - 2v2 Doubles: Up to 4 players (P1/P3 = Near Team, P2/P4 = Far Team) ONLY when 3-4 distinct players are active.
"""

from typing import List, Dict, Any, Optional
import numpy as np

from ml.tracking.deep_eiou import match_tracks


class PlayerTracker:
    def __init__(self, smoothing_alpha: float = 0.40):
        self.smoothing_alpha = smoothing_alpha
        # Permanent tracks dictionary: 1: P1, 2: P2, 3: P3, 4: P4
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self.missing_counts: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0}
        self.max_hold_frames = 12
        self.multi_player_frame_count = 0
        self.total_frames_tracked = 0
        self.is_doubles_mode = False

    def update(self, detections: List[Dict[str, Any]], frame_idx: int) -> List[Dict[str, Any]]:
        """
        Associates detections with permanent Player tracks.
        Enforces physical separation and eliminates duplicate/overlapping tracks.
        """
        self.total_frames_tracked += 1

        # 1. Deduplicate raw detections (if two bounding boxes overlap or centers are < 50px apart)
        deduped = []
        for d in detections:
            bc = d["bottom_center"]
            is_dup = False
            for existing in deduped:
                ebc = existing["bottom_center"]
                if np.hypot(bc[0] - ebc[0], bc[1] - ebc[1]) < 55:
                    is_dup = True
                    break
            if not is_dup:
                deduped.append(d)

        near_dets = [d for d in deduped if d.get("role") == "near"]
        far_dets = [d for d in deduped if d.get("role") == "far"]

        # Only activate doubles mode if there are >= 3 distinct, separated players in >= 35% of frames
        if len(deduped) >= 3 or len(near_dets) >= 2 or len(far_dets) >= 2:
            self.multi_player_frame_count += 1
            # Require sustained multi-player detections: ≥50% of frames AND ≥30 frames observed
            # This prevents brief referee leak-through from triggering doubles mode in a singles match
            if self.total_frames_tracked >= 30 and (self.multi_player_frame_count / self.total_frames_tracked) > 0.50:
                self.is_doubles_mode = True

        tracked_players = []

        # --- Update Near Court ---
        near_tracked = self._track_court_side(
            candidates=near_dets,
            primary_id=1,
            secondary_id=3,
            side_label="Gần",
            frame_idx=frame_idx,
        )
        tracked_players.extend(near_tracked)

        # --- Update Far Court ---
        far_tracked = self._track_court_side(
            candidates=far_dets,
            primary_id=2,
            secondary_id=4,
            side_label="Xa",
            frame_idx=frame_idx,
        )
        tracked_players.extend(far_tracked)

        # Final safety check: remove any tracks that are overlapping (< 50px apart)
        final_players = []
        for p in tracked_players:
            p_bc = p["bottom_center"]
            overlap = False
            for existing in final_players:
                e_bc = existing["bottom_center"]
                if np.hypot(p_bc[0] - e_bc[0], p_bc[1] - e_bc[1]) < 45:
                    overlap = True
                    break
            if not overlap:
                final_players.append(p)

        return final_players

    def _track_court_side(
        self,
        candidates: List[Dict[str, Any]],
        primary_id: int,
        secondary_id: int,
        side_label: str,
        frame_idx: int,
    ) -> List[Dict[str, Any]]:
        results = []

        if len(candidates) == 0:
            # Hold primary player if recently seen
            if primary_id in self.tracks and self.missing_counts[primary_id] < self.max_hold_frames:
                self.missing_counts[primary_id] += 1
                held = dict(self.tracks[primary_id])
                held["frame_idx"] = frame_idx
                held["confidence"] = max(0.35, held["confidence"] * 0.94)
                results.append(self._public_track(held))
            return results

        if len(candidates) == 1 or not self.is_doubles_mode:
            # Exactly 1 player on this side: update primary player ONLY
            cand = candidates[0]
            self.missing_counts[primary_id] = 0
            self.tracks[primary_id] = self._build_smoothed_track(primary_id, cand, side_label, frame_idx)
            results.append(self._public_track(self.tracks[primary_id]))
            # Reset secondary missing count so it doesn't linger as a ghost
            self.missing_counts[secondary_id] = 999
            return results

        # 2 distinct candidates in Doubles mode
        c0, c1 = candidates[0], candidates[1]

        # Spatial matching with previous positions
        if primary_id in self.tracks and secondary_id in self.tracks:
            assignment = match_tracks(
                [self.tracks[primary_id], self.tracks[secondary_id]],
                [c0, c1],
            )
            cand_primary = [c0, c1][assignment[0]]
            cand_secondary = [c0, c1][assignment[1]]
        else:
            # Sort left to right
            if c0["bottom_center"][0] <= c1["bottom_center"][0]:
                cand_primary, cand_secondary = c0, c1
            else:
                cand_primary, cand_secondary = c1, c0

        self.missing_counts[primary_id] = 0
        self.missing_counts[secondary_id] = 0

        self.tracks[primary_id] = self._build_smoothed_track(primary_id, cand_primary, side_label, frame_idx)
        self.tracks[secondary_id] = self._build_smoothed_track(secondary_id, cand_secondary, side_label, frame_idx)

        results.append(self._public_track(self.tracks[primary_id]))
        results.append(self._public_track(self.tracks[secondary_id]))

        return results

    def _build_smoothed_track(
        self, p_id: int, cand: Dict[str, Any], side_label: str, frame_idx: int
    ) -> Dict[str, Any]:
        embedding = self._blend_embedding(
            self.tracks.get(p_id, {}).get("embedding"), cand.get("embedding")
        )
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
            return {
                "player_id": p_id,
                "label": f"VĐV {p_id} ({side_label})",
                "bbox": smoothed_bbox,
                "bottom_center": smoothed_bc,
                "confidence": cand["confidence"],
                "frame_idx": frame_idx,
                "embedding": embedding,
            }
        else:
            return {
                "player_id": p_id,
                "label": f"VĐV {p_id} ({side_label})",
                "bbox": cand["bbox"],
                "bottom_center": cand["bottom_center"],
                "confidence": cand["confidence"],
                "frame_idx": frame_idx,
                "embedding": embedding,
            }

    @staticmethod
    def _blend_embedding(previous: Any, current: Any) -> Optional[np.ndarray]:
        if current is None:
            return previous
        current_array = np.asarray(current, dtype=np.float32).reshape(-1)
        if previous is None:
            norm = np.linalg.norm(current_array)
            return current_array / max(float(norm), 1e-12)
        previous_array = np.asarray(previous, dtype=np.float32).reshape(-1)
        if previous_array.shape != current_array.shape:
            return current_array / max(float(np.linalg.norm(current_array)), 1e-12)
        blended = 0.85 * previous_array + 0.15 * current_array
        return blended / max(float(np.linalg.norm(blended)), 1e-12)

    @staticmethod
    def _public_track(track: Dict[str, Any]) -> Dict[str, Any]:
        public = dict(track)
        public.pop("embedding", None)
        return public
