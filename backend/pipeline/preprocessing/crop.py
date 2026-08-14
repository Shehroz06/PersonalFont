"""Stage 3: trim residual borders left over from the perspective warp.

If the photographed page didn't perfectly fill the source image, or the
detected corners were slightly off, warpPerspective can leave thin
black/empty borders around the rectified page. This crops the image down
to the bounding box of non-empty content, rather than blindly cutting a
fixed margin.
"""

from __future__ import annotations

import cv2
import numpy as np


def autocrop_borders(image: np.ndarray, threshold: int = 10) -> np.ndarray:
    """Crop ``image`` to the bounding box of pixels brighter than ``threshold``.

    Returns the image unchanged if no content is found (fully empty image).
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

    mask = gray > threshold
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)

    if not rows.any() or not cols.any():
        return image

    top, bottom = np.where(rows)[0][[0, -1]]
    left, right = np.where(cols)[0][[0, -1]]

    return image[top : bottom + 1, left : right + 1]
