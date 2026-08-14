"""Fits the transform mapping a photographed page onto template pixel
space, using detected ArUco marker corners as correspondence points.

Using all 4 corners of each matched marker (rather than just its center)
gives more, better-distributed correspondence points for
cv2.findHomography, and lets us measure reprojection error directly in
pixels as an alignment-quality signal.
"""

from __future__ import annotations

import cv2
import numpy as np

from pipeline.alignment.marker_detection import DetectedMarker


def estimate_homography(
    matched_markers: list[DetectedMarker],
    expected_corners_px: dict[int, np.ndarray],
) -> tuple[np.ndarray, float]:
    """Returns (homography_matrix, mean_reprojection_error_px).

    ``matched_markers`` must all have marker_id present in
    ``expected_corners_px``, and there must be at least 3 of them (the
    caller — align.py — is responsible for that precondition, so the
    "not enough markers" error message can describe it in template/page
    terms rather than a raw linear-algebra failure here).
    """
    src_points = []
    dst_points = []
    for marker in matched_markers:
        src_points.append(marker.corners)
        dst_points.append(expected_corners_px[marker.marker_id])

    src = np.concatenate(src_points, axis=0)
    dst = np.concatenate(dst_points, axis=0)

    homography, _mask = cv2.findHomography(src, dst, cv2.RANSAC, ransacReprojThreshold=5.0)

    projected = cv2.perspectiveTransform(src.reshape(-1, 1, 2), homography).reshape(-1, 2)
    mean_error = float(np.linalg.norm(projected - dst, axis=1).mean())

    return homography, mean_error
