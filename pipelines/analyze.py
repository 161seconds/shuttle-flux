"""
End-to-End Match Analytics Pipeline:
Aggregates transformed frame tracking data into complete match statistics, player profiles, rallies, and heatmaps.
"""

from typing import Dict, Any, List, Tuple
import numpy as np
from analytics.movement import (
    smooth_court_trajectory,
    compute_distance_meters,
    compute_speed_profile,
    compute_zone_occupancy,
    compute_voronoi_court_control,
)
from analytics.heatmap import generate_court_heatmap
from analytics.rally import RallySegmenter
from analytics.shots import detect_hits_and_shots


def run_full_analytics(
    frame_records: List[Dict[str, Any]],
    fps: float,
    match_metadata: Dict[str, Any],
    is_doubles: bool = False,
) -> Dict[str, Any]:
    """
    Computes complete match analytics from calibrated tracking frame records.
    Each record contains:
      - frame_idx: int
      - timestamp: float
      - players: List[Dict with 'player_id', 'x_norm', 'y_norm', 'bbox']
      - shuttle: Dict with 'x_norm', 'y_norm', 'visible', 'confidence', 'speed_norm'
    """
    if not frame_records:
        return {"error": "No frame records provided"}

    total_frames = len(frame_records)
    duration_sec = total_frames / fps if fps > 0 else 0.0

    # 1. Separate player trajectories by player_id
    player_trajectories: Dict[int, List[Tuple[float, float]]] = {1: [], 2: []}
    player_positions_by_id: Dict[int, List[Dict[str, Any]]] = {1: [], 2: []}
    shuttle_positions: List[Dict[str, Any]] = []

    for f in frame_records:
        t = f["timestamp"]
        frame_idx = f["frame_idx"]

        # Players
        for p in f.get("players", []):
            p_id = p.get("player_id", 1)
            x_norm = p.get("x_norm", 0.5)
            y_norm = p.get("y_norm", 0.5)
            if p_id in player_trajectories:
                player_trajectories[p_id].append((float(x_norm), float(y_norm)))
                player_positions_by_id[p_id].append(
                    {"x_norm": x_norm, "y_norm": y_norm, "timestamp": t, "frame_idx": frame_idx}
                )

        # Shuttle
        shuttle = f.get("shuttle", {})
        if shuttle:
            shuttle_positions.append(
                {
                    "frame_idx": frame_idx,
                    "timestamp": t,
                    "x_norm": shuttle.get("x_norm", 0.5),
                    "y_norm": shuttle.get("y_norm", 0.5),
                    "visible": shuttle.get("visible", False),
                }
            )

    # 2. Compute Voronoi Spatial Court Control
    p1_traj_arr = np.array(player_trajectories[1], dtype=np.float32)
    p2_traj_arr = np.array(player_trajectories[2], dtype=np.float32)
    voronoi_control = compute_voronoi_court_control(p1_traj_arr, p2_traj_arr)

    # 3. Compute Player Metrics
    player_stats: Dict[str, Any] = {}
    heatmaps: Dict[str, Any] = {}

    for p_id in [1, 2]:
        raw_traj = player_trajectories[p_id]
        control_pct = voronoi_control.get(f"player_{p_id}_control_pct", 50.0)
        if raw_traj:
            smoothed_traj = smooth_court_trajectory(raw_traj, window_size=5)
            speed_profile = compute_speed_profile(smoothed_traj, fps=fps, is_doubles=is_doubles)
            occupancy = compute_zone_occupancy(smoothed_traj)
            heatmap = generate_court_heatmap(raw_traj, grid_size=(30, 60))

            player_stats[f"player_{p_id}"] = {
                "player_id": p_id,
                "label": f"Player {p_id}",
                "side": "Near Court (Bottom)" if p_id == 1 else "Far Court (Top)",
                "distance_meters": speed_profile["total_distance_m"],
                "avg_speed_mps": speed_profile["avg_speed_mps"],
                "max_speed_mps": speed_profile["max_speed_mps"],
                "active_time_seconds": speed_profile["active_seconds"],
                "court_control_pct": control_pct,
                "zone_occupancy": occupancy,
            }
            heatmaps[f"player_{p_id}"] = heatmap
        else:
            player_stats[f"player_{p_id}"] = {
                "player_id": p_id,
                "label": f"Player {p_id}",
                "distance_meters": 0.0,
                "avg_speed_mps": 0.0,
                "max_speed_mps": 0.0,
                "active_time_seconds": 0.0,
                "court_control_pct": control_pct,
                "zone_occupancy": {},
            }
            heatmaps[f"player_{p_id}"] = {"grid": [], "max_density": 0.0}

    # 4. Rally Segmentation
    segmenter = RallySegmenter(fps=fps)
    rallies = segmenter.segment(frame_records)

    # 5. Hit Detection & Shot Categorization
    hits = detect_hits_and_shots(shuttle_positions, player_positions_by_id, fps=fps)

    # 6. Build Final Aggregated Result
    return {
        "metadata": {
            **match_metadata,
            "fps": round(fps, 2),
            "total_frames": total_frames,
            "duration_seconds": round(duration_sec, 2),
        },
        "overview": {
            "total_rallies": len(rallies),
            "total_shots": len(hits),
            "active_play_duration_sec": round(sum(r["duration_seconds"] for r in rallies), 2),
            "total_distance_player_1_m": player_stats.get("player_1", {}).get("distance_meters", 0.0),
            "total_distance_player_2_m": player_stats.get("player_2", {}).get("distance_meters", 0.0),
            "court_control": voronoi_control,
        },
        "players": player_stats,
        "rallies": rallies,
        "hits": hits,
        "heatmaps": heatmaps,
    }
