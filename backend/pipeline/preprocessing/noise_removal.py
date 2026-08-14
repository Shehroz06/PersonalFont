"""Stage 5: noise removal on a grayscale page image.

Uses a median blur (fast, and good at removing the salt-and-pepper /
paper-texture noise typical of phone photos) followed by a light bilateral
filter (smooths shading/lighting noise while keeping stroke edges sharp,
which matters for later thresholding and vectorization).
"""

from __future__ import annotations

import cv2
import numpy as np


def remove_noise(
    gray_image: np.ndarray,
    median_ksize: int = 3,
    bilateral_d: int = 5,
    bilateral_sigma: int = 50,
) -> np.ndarray:
    denoised = cv2.medianBlur(gray_image, median_ksize)
    denoised = cv2.bilateralFilter(denoised, bilateral_d, bilateral_sigma, bilateral_sigma)
    return denoised
