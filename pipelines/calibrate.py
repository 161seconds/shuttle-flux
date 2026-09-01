"""
Court Calibration and Homography Pipeline:
Computes the 3x3 Homography Matrix H and transforms points between Camera Image and 2D Court Plane.
Supports both OpenCV and pure NumPy Direct Linear Transformation (DLT).
"""

from typing import List, Tuple, Optional, Dict, Any
import numpy as np
from analytics.court import get_standard_court_keypoints, normalize_court_coordinates, SINGLES_WIDTH_M, COURT_LENGTH_M

try:
    import cv2
    HAS_OPENCV = True
except ImportError:
    HAS_OPENCV = False

try:
    from sports.common.view import ViewTransformer
    HAS_ROBOFLOW_SPORTS = True
except ImportError:
    HAS_ROBOFLOW_SPORTS = False


def compute_dlt_homography(
    src_points: List[Tuple[float, float]],
    dst_points: List[Tuple[float, float]],
) -> Optional[np.ndarray]:
    """
    Computes 3x3 Homography matrix H using Direct Linear Transformation (DLT) via SVD.
    Requires at least 4 non-collinear point correspondences.
    """
    if len(src_points) < 4 or len(dst_points) < 4:
        return None

    A = []
    for (x, y), (u, v) in zip(src_points, dst_points):
        A.append([-x, -y, -1, 0, 0, 0, u * x, u * y, u])
        A.append([0, 0, 0, -x, -y, -1, v * x, v * y, v])

    A = np.array(A, dtype=np.float64)
    # SVD: A = U S V^T
    _, _, Vh = np.linalg.svd(A)
    # Last row of Vh is the solution
    H = Vh[-1].reshape((3, 3))

    if np.abs(H[2, 2]) > 1e-8:
        H = H / H[2, 2]

    return H


class CourtCalibrator:
    """
    Handles perspective transformation mapping camera pixels to normalized [0, 1] court coordinates.
    Utilizes Roboflow ViewTransformer and OpenCV/NumPy Homography estimation.
    """

    def __init__(self, is_doubles: bool = False):
        self.is_doubles = is_doubles
        self.H: Optional[np.ndarray] = None
        self.H_inv: Optional[np.ndarray] = None
        self.transformer: Optional[Any] = None
        self.court_keypoints_metric = get_standard_court_keypoints(is_doubles)

    def calibrate_from_points(
        self,
        src_image_points: List[Tuple[float, float]],
        dst_court_points_norm: List[Tuple[float, float]],
    ) -> bool:
        """
        Computes Homography matrix H from matching pairs of image and normalized court points.
        """
        if len(src_image_points) < 4 or len(dst_court_points_norm) < 4:
            return False

        if HAS_ROBOFLOW_SPORTS:
            try:
                self.transformer = ViewTransformer(
                    source=np.array(src_image_points, dtype=np.float32),
                    target=np.array(dst_court_points_norm, dtype=np.float32),
                )
            except Exception:
                self.transformer = None

        if HAS_OPENCV:
            src_pts = np.array(src_image_points, dtype=np.float32).reshape(-1, 1, 2)
            dst_pts = np.array(dst_court_points_norm, dtype=np.float32).reshape(-1, 1, 2)
            H, status = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        else:
            H = compute_dlt_homography(src_image_points, dst_court_points_norm)

        if H is None:
            return False

        self.H = H
        try:
            self.H_inv = np.linalg.inv(H)
        except np.linalg.LinAlgError:
            self.H_inv = None
            return False

        return True

    def calibrate_standard_corners(
        self,
        bottom_left_px: Tuple[float, float],
        bottom_right_px: Tuple[float, float],
        top_left_px: Tuple[float, float],
        top_right_px: Tuple[float, float],
    ) -> bool:
        """Convenience method to calibrate using the 4 main court corners."""
        src = [bottom_left_px, bottom_right_px, top_left_px, top_right_px]
        dst = [(0.0, 0.0), (1.0, 0.0), (0.0, 1.0), (1.0, 1.0)]
        return self.calibrate_from_points(src, dst)

    def transform_image_to_court(
        self, image_points: np.ndarray, clip_bounds: bool = True
    ) -> np.ndarray:
        """
        Transforms pixel points (N, 2) to normalized court plane [0, 1].
        """
        if len(image_points) == 0:
            return np.empty((0, 2), dtype=np.float32)

        if self.transformer is not None:
            try:
                pts = np.array(image_points, dtype=np.float32)
                transformed = self.transformer.transform_points(pts)
                if clip_bounds:
                    transformed[:, 0] = np.clip(transformed[:, 0], 0.0, 1.0)
                    transformed[:, 1] = np.clip(transformed[:, 1], 0.0, 1.0)
                return transformed.astype(np.float32)
            except Exception:
                pass

        if self.H is None:
            return np.empty((0, 2), dtype=np.float32)

        pts = np.array(image_points, dtype=np.float64)
        # Homogeneous coordinates (N, 3)
        ones = np.ones((pts.shape[0], 1), dtype=np.float64)
        homogeneous = np.hstack([pts, ones])

        transformed_h = homogeneous @ self.H.T
        transformed = transformed_h[:, :2] / transformed_h[:, 2:3]

        if clip_bounds:
            transformed[:, 0] = np.clip(transformed[:, 0], 0.0, 1.0)
            transformed[:, 1] = np.clip(transformed[:, 1], 0.0, 1.0)

        return transformed.astype(np.float32)

    def transform_court_to_image(self, court_points_norm: np.ndarray) -> np.ndarray:
        """
        Transforms normalized court coordinates [0, 1] to camera pixel coordinates (N, 2).
        """
        if self.H_inv is None or len(court_points_norm) == 0:
            return np.empty((0, 2), dtype=np.float32)

        pts = np.array(court_points_norm, dtype=np.float64)
        ones = np.ones((pts.shape[0], 1), dtype=np.float64)
        homogeneous = np.hstack([pts, ones])

        transformed_h = homogeneous @ self.H_inv.T
        transformed = transformed_h[:, :2] / transformed_h[:, 2:3]

        return transformed.astype(np.float32)


def compute_homography(
    src_points: List[Tuple[float, float]],
    dst_points: List[Tuple[float, float]],
) -> Optional[np.ndarray]:
    """Helper function to calculate Homography matrix."""
    return compute_dlt_homography(src_points, dst_points)
