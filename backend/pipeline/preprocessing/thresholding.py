"""Stage 6: binarize the page.

Convention used throughout the rest of the pipeline: the output is a
binary image where **ink/foreground pixels are 255 (white)** and
background is 0 (black) — i.e. inverted relative to the original scan.
This matches what cv2.findContours and downstream segmentation/validation
stages expect, and downstream stages must not re-invent this convention.
"""

from __future__ import annotations

import cv2
import numpy as np


def binarize_otsu(gray_image: np.ndarray) -> np.ndarray:
    _, binary = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return binary


def binarize_adaptive(
    gray_image: np.ndarray,
    block_size: int = 35,
    c: int = 15,
) -> np.ndarray:
    """Adaptive thresholding — more robust than Otsu under uneven lighting
    or shadows (NFR-02), at the cost of being more sensitive to noise."""
    return cv2.adaptiveThreshold(
        gray_image,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block_size,
        c,
    )
