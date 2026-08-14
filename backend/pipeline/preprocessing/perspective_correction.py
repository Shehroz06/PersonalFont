"""Stage 2: warp the photographed page to a flat, top-down rectangle.

Takes the 4 corners found by page_detection and produces a rectified image
of a caller-specified pixel size. Kept generic (no template/DPI knowledge)
so it can be unit tested with synthetic quadrilaterals.
"""

from __future__ import annotations

import cv2
import numpy as np

from pipeline.preprocessing.geometry import order_points


def correct_perspective(
    image: np.ndarray,
    corners: np.ndarray,
    output_size: tuple[int, int],
) -> np.ndarray:
    """Warp ``image`` so the quadrilateral ``corners`` fills the output.

    ``corners`` need not be pre-ordered — it is re-ordered defensively.
    ``output_size`` is (width, height) in pixels of the rectified result.
    """
    width, height = output_size
    src = order_points(corners)
    dst = np.array(
        [
            [0, 0],
            [width - 1, 0],
            [width - 1, height - 1],
            [0, height - 1],
        ],
        dtype=np.float32,
    )

    matrix = cv2.getPerspectiveTransform(src, dst)
    return cv2.warpPerspective(image, matrix, (width, height))
