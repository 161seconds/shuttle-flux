"""
Player Movement Analytics:
- Coordinate Smoothing (Moving average & Exponential smoothing)
- Total Distance Travelled (metric meters)
- Velocity & Speed Profile (Average, Max, Instantaneous)
- Acceleration & Bursts
- Tactical Zone Occupancy Distribution
"""

from typing import Dict, List, Tuple, Any
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
    positions_norm: np.ndarray, fps: float, is_doubles: bool = False
) -> Dict[str, Any]:
    """
    Computes speed metrics:
    - instantaneous speeds (m/s)
    - average speed (m/s)
    - max speed (m/s)
    - active moving time (seconds)
    """
    if len(positions_norm) < 2 or fps <= 0:
        return {
            "instantaneous_speeds_mps": [],
            "avg_speed_mps": 0.0,
            "max_speed_mps": 0.0,
            "total_distance_m": 0.0,
            "active_seconds": 0.0,
        }

    dt = 1.0 / fps
    width = 6.10 if is_doubles else 5.18
    length = 13.40

    dx = np.diff(positions_norm[:, 0]) * width
    dy = np.diff(positions_norm[:, 1]) * length
    step_distances = np.sqrt(dx**2 + dy**2)

    instantaneous_speeds = step_distances / dt

    # Filter out unrealistic instantaneous speeds (> 12 m/s for human movement) as noise
    filtered_speeds = np.clip(instantaneous_speeds, 0.0, 12.0)

    # Threshold for considering player "active/moving" vs standing (0.3 m/s)
    moving_mask = filtered_speeds > 0.3
    active_seconds = float(np.sum(moving_mask) * dt)

    avg_speed = float(np.mean(filtered_speeds)) if len(filtered_speeds) > 0 else 0.0
    max_speed = float(np.percentile(filtered_speeds, 98)) if len(filtered_speeds) > 0 else 0.0
    total_dist = float(np.sum(step_distances))

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
