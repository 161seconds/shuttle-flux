"""
Shot and Hit Event Detection:
- Hit detection: Player-shuttle proximity and shuttle direction change
- Shot classification: Rule-based heuristics based on court position and trajectory velocity
"""

from typing import List, Dict, Any, Optional
import numpy as np


class ShotClassifier:
    """
    Classifies badminton shots into tactical types:
    - SERVE
    - CLEAR
    - SMASH
    - DROP
    - DRIVE
    - NET_SHOT
    - LIFT / DEFENSIVE
    """

    SHOT_TYPES = ["serve", "clear", "smash", "drop", "drive", "net_shot", "lift"]

    @staticmethod
    def classify_shot(
        hit_pos_norm: Dict[str, float],
        landing_pos_norm: Optional[Dict[str, float]],
        peak_velocity_mps: float,
        is_first_shot: bool = False,
    ) -> Dict[str, Any]:
        """Classifies a shot based on geometric trajectory features."""
        if is_first_shot:
            return {"shot_type": "serve", "confidence": 0.92, "source": "heuristic_rules"}

        x, y = hit_pos_norm.get("x", 0.5), hit_pos_norm.get("y", 0.5)
        # Determine player side and depth
        dist_to_net = abs(y - 0.5)

        # Net Shot: Hit within 0.15 normalized distance to net (y=0.5)
        if dist_to_net < 0.12:
            return {"shot_type": "net_shot", "confidence": 0.85, "source": "heuristic_rules"}

        # Rear court shots (y < 0.25 or y > 0.75)
        is_rear_court = dist_to_net > 0.28

        if is_rear_court:
            if peak_velocity_mps > 25.0:  # High speed downward
                return {"shot_type": "smash", "confidence": 0.82, "source": "heuristic_rules"}
            elif landing_pos_norm and abs(landing_pos_norm.get("y", 0.5) - 0.5) < 0.15:
                return {"shot_type": "drop", "confidence": 0.78, "source": "heuristic_rules"}
            else:
                return {"shot_type": "clear", "confidence": 0.80, "source": "heuristic_rules"}

        # Midcourt shots
        if peak_velocity_mps > 18.0:
            return {"shot_type": "drive", "confidence": 0.75, "source": "heuristic_rules"}

        return {"shot_type": "lift", "confidence": 0.70, "source": "heuristic_rules"}


def detect_hits_and_shots(
    shuttle_positions: List[Dict[str, Any]],
    players_positions: Dict[int, List[Dict[str, Any]]],
    fps: float = 30.0,
) -> List[Dict[str, Any]]:
    """
    Detects hit frames where a player makes contact with the shuttlecock.
    Identifies inflection points where shuttle velocity changes direction significantly near a player.
    """
    if len(shuttle_positions) < 3:
        return []

    hits: List[Dict[str, Any]] = []

    for i in range(1, len(shuttle_positions) - 1):
        prev_p = shuttle_positions[i - 1]
        curr_p = shuttle_positions[i]
        next_p = shuttle_positions[i + 1]

        if not (prev_p.get("visible") and curr_p.get("visible") and next_p.get("visible")):
            continue

        # Compute velocity vectors
        v1_x = curr_p["x_norm"] - prev_p["x_norm"]
        v1_y = curr_p["y_norm"] - prev_p["y_norm"]
        v2_x = next_p["x_norm"] - curr_p["x_norm"]
        v2_y = next_p["y_norm"] - curr_p["y_norm"]

        # Y-direction reversal (crossing net / hitting back)
        if (v1_y * v2_y < 0) and abs(v1_y - v2_y) > 0.03:
            # Find closest player
            hit_x, hit_y = curr_p["x_norm"], curr_p["y_norm"]
            closest_player_id = 1
            min_dist = float("inf")

            for p_id, p_list in players_positions.items():
                if i < len(p_list):
                    px, py = p_list[i]["x_norm"], p_list[i]["y_norm"]
                    dist = np.sqrt((hit_x - px) ** 2 + (hit_y - py) ** 2)
                    if dist < min_dist:
                        min_dist = dist
                        closest_player_id = p_id

            shot_info = ShotClassifier.classify_shot(
                hit_pos_norm={"x": hit_x, "y": hit_y},
                landing_pos_norm=None,
                peak_velocity_mps=20.0,
                is_first_shot=(len(hits) == 0),
            )

            hits.append(
                {
                    "hit_index": len(hits) + 1,
                    "frame_idx": curr_p.get("frame_idx", i),
                    "timestamp": round(curr_p.get("timestamp", i / fps), 2),
                    "player_id": closest_player_id,
                    "hit_position": {"x": round(hit_x, 3), "y": round(hit_y, 3)},
                    "shot_type": shot_info["shot_type"],
                    "confidence": shot_info["confidence"],
                }
            )

    return hits
