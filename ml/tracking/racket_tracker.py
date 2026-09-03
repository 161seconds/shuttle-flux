"""Associates racket detections with athlete wrists and smooths short dropouts."""

from typing import Any, Dict, List

import numpy as np


class RacketTracker:
    def __init__(self, smoothing_alpha: float = 0.55, max_hold_frames: int = 4):
        self.smoothing_alpha = smoothing_alpha
        self.max_hold_frames = max_hold_frames
        self.tracks: Dict[int, Dict[str, Any]] = {}
        self.missing: Dict[int, int] = {}

    @staticmethod
    def _owner_distance(racket: Dict[str, Any], player: Dict[str, Any]) -> float:
        center = np.asarray(racket["center"], dtype=np.float32)
        pose = (player.get("pose") or {}).get("keypoints", {})
        wrists = [
            values
            for name in ("left_wrist", "right_wrist")
            if (values := pose.get(name)) is not None and values[2] >= 0.25
        ]
        if wrists:
            return min(float(np.linalg.norm(center - np.asarray(wrist[:2]))) for wrist in wrists)
        x1, y1, x2, y2 = player["bbox"]
        player_center = np.asarray([(x1 + x2) / 2.0, (y1 + y2) / 2.0])
        return float(np.linalg.norm(center - player_center))

    @staticmethod
    def _attach_skeleton(
        racket: Dict[str, Any], player: Dict[str, Any]
    ) -> Dict[str, Any]:
        result = dict(racket)
        pose = (player.get("pose") or {}).get("keypoints", {})
        wrists = [
            values
            for name in ("left_wrist", "right_wrist")
            if (values := pose.get(name)) is not None and values[2] >= 0.20
        ]
        if not wrists:
            return result

        center = np.asarray(racket["center"], dtype=np.float32)
        wrist = min(
            wrists,
            key=lambda point: float(
                np.linalg.norm(center - np.asarray(point[:2], dtype=np.float32))
            ),
        )
        keypoints = dict(result.get("keypoints") or {})
        keypoints["wrist"] = list(wrist)
        if "handle" not in keypoints or "head_center" not in keypoints:
            handle = np.asarray(wrist[:2], dtype=np.float32)
            direction = center - handle
            length = float(np.linalg.norm(direction))
            if length <= 1e-6:
                return result
            x1, y1, x2, y2 = racket["bbox"]
            tip = center + direction / length * float(np.hypot(x2 - x1, y2 - y1)) * 0.45
            keypoints.update(
                {
                    "handle": [round(float(handle[0]), 1), round(float(handle[1]), 1), wrist[2]],
                    "head_center": [round(float(center[0]), 1), round(float(center[1]), 1), racket["confidence"]],
                    "tip": [round(float(tip[0]), 1), round(float(tip[1]), 1), racket["confidence"]],
                }
            )
        result["keypoints"] = keypoints
        return result

    def _smooth(self, previous: Dict[str, Any], current: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(current)
        for key in ("bbox", "center"):
            old = np.asarray(previous[key], dtype=np.float32)
            new = np.asarray(current[key], dtype=np.float32)
            result[key] = np.round(
                (1.0 - self.smoothing_alpha) * old + self.smoothing_alpha * new, 1
            ).tolist()
        frame_delta = max(1, int(current["frame_idx"] - previous.get("frame_idx", current["frame_idx"] - 1)))
        velocity = (
            np.asarray(result["center"], dtype=np.float32)
            - np.asarray(previous["center"], dtype=np.float32)
        ) / frame_delta
        result["velocity_px_per_frame"] = np.round(velocity, 2).tolist()
        result["speed_px_per_frame"] = round(float(np.linalg.norm(velocity)), 2)
        return result

    def update(
        self, rackets: List[Dict[str, Any]], players: List[Dict[str, Any]], frame_idx: int
    ) -> List[Dict[str, Any]]:
        candidates = []
        for racket in rackets:
            if not players:
                continue
            owner = min(players, key=lambda player: self._owner_distance(racket, player))
            x1, y1, x2, y2 = owner["bbox"]
            max_distance = max(80.0, float(np.hypot(x2 - x1, y2 - y1)) * 0.9)
            distance = self._owner_distance(racket, owner)
            if distance <= max_distance:
                candidate = dict(racket)
                candidate = self._attach_skeleton(candidate, owner)
                candidate["owner_id"] = owner["player_id"]
                candidate["frame_idx"] = frame_idx
                candidate["wrist_distance"] = round(distance, 1)
                candidates.append(candidate)

        best_by_owner: Dict[int, Dict[str, Any]] = {}
        for candidate in candidates:
            owner_id = candidate["owner_id"]
            existing = best_by_owner.get(owner_id)
            if existing is None or candidate["wrist_distance"] < existing["wrist_distance"]:
                best_by_owner[owner_id] = candidate

        output = []
        player_ids = {player["player_id"] for player in players}
        for owner_id in player_ids:
            candidate = best_by_owner.get(owner_id)
            if candidate is not None:
                if owner_id in self.tracks:
                    candidate = self._smooth(self.tracks[owner_id], candidate)
                self.tracks[owner_id] = candidate
                self.missing[owner_id] = 0
                candidate.setdefault("velocity_px_per_frame", [0.0, 0.0])
                candidate.setdefault("speed_px_per_frame", 0.0)
                output.append(dict(candidate))
            elif owner_id in self.tracks and self.missing.get(owner_id, 0) < self.max_hold_frames:
                self.missing[owner_id] = self.missing.get(owner_id, 0) + 1
                held = dict(self.tracks[owner_id])
                held["frame_idx"] = frame_idx
                held["confidence"] = round(max(0.05, held["confidence"] * 0.85), 3)
                held["speed_px_per_frame"] = round(
                    float(held.get("speed_px_per_frame", 0.0)) * 0.65, 2
                )
                output.append(held)
        return output
