"""Stage 7: correct minor residual rotation left after perspective
correction (e.g. the page was aligned but the paper itself sat a couple
degrees askew under the camera).

Operates on the binary image (ink=255 on background=0, see
thresholding.py) so the skew estimate is based on ink pixels only, not
scan artifacts.
"""

from __future__ import annotations

import cv2
import numpy as np

from pipeline.preprocessing.errors import DeskewError

# Skew angles beyond this are assumed to be a page-detection/alignment
# failure rather than "minor" skew this stage is meant to fix.
MAX_CORRECTABLE_SKEW_DEGREES = 15.0


def estimate_skew_angle(binary_image: np.ndarray) -> float:
    """Return the estimated skew angle in degrees (positive = clockwise).

    Raises DeskewError if there isn't enough ink to estimate an angle from
    (e.g. a blank or near-empty page).
    """
    coords = cv2.findNonZero(binary_image)
    if coords is None or len(coords) < 50:
        raise DeskewError(
            "Not enough content was found on the page to estimate its "
            "rotation. The page may be blank, unwritten, or the "
            "thresholding step failed to pick up any ink."
        )

    raw_angle = cv2.minAreaRect(coords)[-1]

    # cv2.minAreaRect's angle convention has varied across OpenCV versions
    # ([0, 90) in current releases, (-90, 0] in older ones). This formula
    # normalizes either convention to the nearest rotation in (-45, 45],
    # which is also directly the angle getRotationMatrix2D needs to undo
    # it (verified empirically against cv2.warpAffine's rotation sign).
    return ((raw_angle + 45) % 90) - 45


def deskew(binary_image: np.ndarray, angle: float | None = None) -> tuple[np.ndarray, float]:
    """Rotate ``binary_image`` to correct its skew.

    Returns (deskewed_image, angle_applied_degrees). If the estimated (or
    supplied) angle is larger than MAX_CORRECTABLE_SKEW_DEGREES, the image
    is returned unrotated with angle 0.0 rather than applying a large,
    likely-wrong rotation.
    """
    if angle is None:
        angle = estimate_skew_angle(binary_image)

    if abs(angle) > MAX_CORRECTABLE_SKEW_DEGREES:
        return binary_image, 0.0

    height, width = binary_image.shape[:2]
    center = (width / 2, height / 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        binary_image,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return rotated, angle
