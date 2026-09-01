"""
Heatmap Generation:
Computes 2D Gaussian kernel density matrices representing spatial coverage on the badminton court.
"""

from typing import List, Tuple, Dict, Any
import numpy as np


def generate_court_heatmap(
    positions_norm: List[Tuple[float, float]],
    grid_size: Tuple[int, int] = (50, 100),
    sigma: float = 2.5,
) -> Dict[str, Any]:
    """
    Computes a 2D Gaussian-smoothed density grid.
    - positions_norm: List of (norm_x, norm_y) coordinates in [0, 1]
    - grid_size: (width_cells, length_cells), default (50, 100)
    - sigma: Gaussian smoothing radius in grid cells

    Returns serializable dictionary containing:
    - grid: 2D list of normalized intensity values [0.0 - 1.0]
    - max_density: peak count before normalization
    - grid_size: (w, h)
    """
    w_cells, h_cells = grid_size
    raw_grid = np.zeros((w_cells, h_cells), dtype=np.float32)

    if not positions_norm:
        return {
            "grid": raw_grid.tolist(),
            "max_density": 0.0,
            "grid_size": [w_cells, h_cells],
        }

    # Bin positions into discrete 2D grid cells
    for pos in positions_norm:
        if len(pos) < 2:
            continue
        x, y = float(pos[0]), float(pos[1])
        if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
            gx = min(int(x * w_cells), w_cells - 1)
            gy = min(int(y * h_cells), h_cells - 1)
            raw_grid[gx, gy] += 1.0

    # Apply 2D Gaussian blur
    # Create 1D Gaussian kernel
    radius = int(3 * sigma)
    kernel_1d = np.exp(-0.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
    kernel_1d /= np.sum(kernel_1d)

    # Convolve rows then cols
    smoothed = np.apply_along_axis(lambda m: np.convolve(m, kernel_1d, mode="same"), axis=0, arr=raw_grid)
    smoothed = np.apply_along_axis(lambda m: np.convolve(m, kernel_1d, mode="same"), axis=1, arr=smoothed)

    max_val = float(np.max(smoothed))
    if max_val > 0:
        normalized_grid = smoothed / max_val
    else:
        normalized_grid = smoothed

    return {
        "grid": [[round(float(val), 4) for val in col] for col in normalized_grid],
        "max_density": round(max_val, 2),
        "grid_size": [w_cells, h_cells],
    }
