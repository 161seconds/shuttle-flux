"""
Player Movement Analytics:
- Coordinate Smoothing (Moving average & Exponential smoothing)
- Total Distance Travelled (metric meters)
- Velocity & Speed Profile (Average, Max, Instantaneous)
- Acceleration & Bursts
- Tactical Zone Occupancy Distribution
"""

from typing import Dict, List, Tuple, Any, Optional
import numpy as np
from analytics.court import get_court_zone, denormalize_court_coordinates, SINGLES_WIDTH_M, COURT_LENGTH_M


def smooth_court_trajectory(
    positions_norm: List[Tuple[float, float]], window_size: int = 5
) -> np.ndarray:
    """
    Applies sliding window average filter to eliminate detection jitter.
    Input: List of (norm_x, norm_y) points.
    Output: Array of smoothed (norm_x, norm_y) points.
    """
    if len(positions_norm) < 2:
        return np.array(positions_norm, dtype=np.float32)

    arr = np.array(positions_norm, dtype=np.float32)
    if len(arr) < window_size:
        return arr

    # Symmetric padding to preserve trajectory endpoints
    pad_width = window_size // 2
    padded_x = np.pad(arr[:, 0], pad_width, mode="edge")
    padded_y = np.pad(arr[:, 1], pad_width, mode="edge")

    kernel = np.ones(window_size) / window_size
    smoothed_x = np.convolve(padded_x, kernel, mode="valid")
    smoothed_y = np.convolve(padded_y, kernel, mode="valid")

    # Clip to valid normalized bounds [0, 1]
    smoothed_x = np.clip(smoothed_x, 0.0, 1.0)
    smoothed_y = np.clip(smoothed_y, 0.0, 1.0)

    return np.column_stack((smoothed_x, smoothed_y))


def compute_smoothed_positions(positions: np.ndarray, window_size: int = 5) -> np.ndarray:
    """Applies sliding window smoothing filter to positions array."""
    return smooth_court_trajectory(positions, window_size)


def compute_player_distance(positions_meters: np.ndarray) -> float:
    """Calculates cumulative Euclidean distance across metric coordinate points."""
    if len(positions_meters) < 2:
        return 0.0
    diffs = np.diff(positions_meters, axis=0)
    return float(np.sum(np.sqrt(np.sum(diffs**2, axis=1))))


def compute_distance_meters(
    positions_norm: np.ndarray, is_doubles: bool = False
) -> float:
    """Calculates cumulative metric distance travelled in meters."""
    if len(positions_norm) < 2:
        return 0.0

    width = 6.10 if is_doubles else 5.18
    length = 13.40

    # Convert normalized differences to metric differences
    dx = np.diff(positions_norm[:, 0]) * width
    dy = np.diff(positions_norm[:, 1]) * length

    step_distances = np.sqrt(dx**2 + dy**2)
    return float(np.sum(step_distances))


def compute_speed_profile(
    positions_norm: np.ndarray,
    fps: float,
    is_doubles: bool = False,
    timestamps: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    """
    Computes speed metrics:
    - instantaneous speeds (m/s)
    - average speed (m/s)
    - max speed (m/s)
    - active moving time (seconds)
    """
    if len(positions_norm) < 2 or (timestamps is None and fps <= 0):
        return {
            "instantaneous_speeds_mps": [],
            "avg_speed_mps": 0.0,
            "max_speed_mps": 0.0,
            "total_distance_m": 0.0,
            "active_seconds": 0.0,
        }

    if timestamps is not None:
        timestamps = np.asarray(timestamps, dtype=np.float64)
        if len(timestamps) != len(positions_norm):
            raise ValueError("timestamps must have the same length as positions_norm")
        dt = np.diff(timestamps)
        valid_dt = dt > 0
    else:
        dt = np.full(len(positions_norm) - 1, 1.0 / fps, dtype=np.float64)
        valid_dt = np.ones_like(dt, dtype=bool)

    width = 6.10 if is_doubles else 5.18
    length = 13.40

    dx = np.diff(positions_norm[:, 0]) * width
    dy = np.diff(positions_norm[:, 1]) * length
    step_distances = np.sqrt(dx**2 + dy**2)

    instantaneous_speeds = np.zeros_like(step_distances, dtype=np.float64)
    instantaneous_speeds[valid_dt] = step_distances[valid_dt] / dt[valid_dt]

    # Filter out unrealistic instantaneous speeds (> 12 m/s for human movement) as noise
    filtered_speeds = np.clip(instantaneous_speeds, 0.0, 12.0)

    # Threshold for considering player "active/moving" vs standing (0.3 m/s)
    moving_mask = filtered_speeds > 0.3
    active_seconds = float(np.sum(dt[moving_mask & valid_dt]))

    total_valid_time = float(np.sum(dt[valid_dt]))
    avg_speed = (
        float(np.sum(filtered_speeds[valid_dt] * dt[valid_dt]) / total_valid_time)
        if total_valid_time > 0
        else 0.0
    )
    max_speed = float(np.percentile(filtered_speeds, 98)) if len(filtered_speeds) > 0 else 0.0
    total_dist = float(np.sum(step_distances[valid_dt]))

    return {
        "instantaneous_speeds_mps": [round(float(s), 2) for s in filtered_speeds],
        "avg_speed_mps": round(avg_speed, 2),
        "max_speed_mps": round(max_speed, 2),
        "total_distance_m": round(total_dist, 2),
        "active_seconds": round(active_seconds, 2),
    }


def compute_zone_occupancy(positions_norm: np.ndarray) -> Dict[str, float]:
    """
    Computes the percentage of time spent in each of the 12 tactical court zones.
    Returns: Dict mapping zone names (e.g. 'P1_rear_left') to percentage (0.0 to 100.0).
    """
    if len(positions_norm) == 0:
        return {}

    counts: Dict[str, int] = {}
    total = len(positions_norm)

    for x_norm, y_norm in positions_norm:
        zone = get_court_zone(float(x_norm), float(y_norm))
        counts[zone] = counts.get(zone, 0) + 1

    return {zone: round((cnt / total) * 100.0, 2) for zone, cnt in counts.items()}


def compute_voronoi_court_control(
    p1_positions: np.ndarray, p2_positions: np.ndarray
) -> Dict[str, float]:
    """
    Calculates the percentage of court space dominated by Player 1 vs Player 2
    using Voronoi spatial distance partitioning on a 20x40 sampling grid.
    """
    if len(p1_positions) == 0 or len(p2_positions) == 0:
        return {"player_1_control_pct": 50.0, "player_2_control_pct": 50.0}

    # Generate sampling grid over court [0, 1] x [0, 1]
    gx, gy = np.meshgrid(np.linspace(0, 1, 20), np.linspace(0, 1, 40))
    grid_pts = np.column_stack((gx.ravel(), gy.ravel()))

    p1_wins = 0
    p2_wins = 0

    n_samples = min(len(p1_positions), len(p2_positions))
    # Step through every 5 frames for fast execution
    for i in range(0, n_samples, 5):
        pt1 = p1_positions[i]
        pt2 = p2_positions[i]

        d1 = np.sum((grid_pts - pt1) ** 2, axis=1)
        d2 = np.sum((grid_pts - pt2) ** 2, axis=1)

        p1_wins += int(np.sum(d1 < d2))
        p2_wins += int(np.sum(d2 <= d1))

    total = p1_wins + p2_wins
    if total == 0:
        return {"player_1_control_pct": 50.0, "player_2_control_pct": 50.0}

    p1_pct = round((p1_wins / total) * 100.0, 1)
    p2_pct = round(100.0 - p1_pct, 1)

    return {
        "player_1_control_pct": p1_pct,
        "player_2_control_pct": p2_pct,
    }
