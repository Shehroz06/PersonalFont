"""Detects the ArUco corner markers printed on every template page.

Deliberately independent of page_detection.py (Phase 3): that stage finds
the paper's outline via generic edge/contour detection and knows nothing
about templates. This stage looks for the specific markers generate.py
printed, which is what lets alignment identify *which* template page a
photo shows and compute a precise homography from marker correspondences.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.template_gen.layout import ARUCO_DICTIONARY
from pipeline.preprocessing.grayscale import to_grayscale


@dataclass(frozen=True)
class DetectedMarker:
    marker_id: int
    corners: np.ndarray  # (4, 2) pixel coords, ordered (tl, tr, br, bl)


def detect_markers(image: np.ndarray) -> list[DetectedMarker]:
    """Find every ArUco marker in ``image``. Returns an empty list if none
    are found — callers decide whether that's an error."""
    gray = to_grayscale(image)

    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY)
    detector = cv2.aruco.ArucoDetector(aruco_dict, cv2.aruco.DetectorParameters())
    corners, ids, _rejected = detector.detectMarkers(gray)

    if ids is None:
        return []

    return [
        DetectedMarker(marker_id=int(marker_id), corners=marker_corners.reshape(4, 2).astype(np.float32))
        for marker_corners, marker_id in zip(corners, ids.flatten())
    ]
