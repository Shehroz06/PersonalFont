"""Generic geometry helpers for binary (ink=255/background=0) glyph
images — shared by validation (Phase 6) and normalization (Phase 7) rather
than each re-deriving "how much ink, and where" from scratch.

See pipeline.preprocessing.thresholding for the ink=255/background=0
convention every caller of this module assumes.
"""

from __future__ import annotations

import cv2
import numpy as np


def ink_pixel_count(image: np.ndarray) -> int:
    return int(np.count_nonzero(image))


def ink_bounding_box(image: np.ndarray) -> tuple[int, int, int, int] | None:
    """Tight (x0, y0, x1, y1) bounding box of ink pixels, or None if empty."""
    coords = cv2.findNonZero(image)
    if coords is None:
        return None
    x, y, w, h = cv2.boundingRect(coords)
    return x, y, x + w, y + h
