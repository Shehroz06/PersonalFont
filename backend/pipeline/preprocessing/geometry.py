"""Small geometry helpers shared by the page-detection and
perspective-correction stages. Kept separate so both stages (and their
tests) can rely on the same point-ordering convention without duplicating
it.
"""

from __future__ import annotations

import numpy as np


def order_points(pts: np.ndarray) -> np.ndarray:
    """Order 4 points as (top-left, top-right, bottom-right, bottom-left).

    ``pts`` may be in any order (e.g. straight from cv2.approxPolyDP).
    This is the convention cv2.getPerspectiveTransform expects for both
    the source and destination point arrays.
    """
    pts = pts.reshape(4, 2).astype(np.float32)

    ordered = np.zeros((4, 2), dtype=np.float32)
    total = pts.sum(axis=1)
    ordered[0] = pts[np.argmin(total)]  # top-left: smallest x+y
    ordered[2] = pts[np.argmax(total)]  # bottom-right: largest x+y

    diff = np.diff(pts, axis=1).flatten()
    ordered[1] = pts[np.argmin(diff)]  # top-right: smallest y-x
    ordered[3] = pts[np.argmax(diff)]  # bottom-left: largest y-x

    return ordered
