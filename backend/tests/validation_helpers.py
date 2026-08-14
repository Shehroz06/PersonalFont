"""Synthetic binary glyph crops for the validation tests.

Built directly in the ink=255/background=0 convention (see
pipeline.preprocessing.thresholding) rather than reusing the
segmentation-test fixtures, which are grayscale "scans" (ink=0 on
background=255) representing pre-threshold images — a different stage's
concern. Not a test module itself (no test_ prefix) — pytest won't
collect it.
"""

from __future__ import annotations

import cv2
import numpy as np


def blank_crop(size: tuple[int, int] = (60, 60)) -> np.ndarray:
    return np.zeros(size, dtype=np.uint8)


def clean_letter_crop(size: tuple[int, int] = (60, 60), stroke_thickness: int = 4) -> np.ndarray:
    """A single, well-formed connected stroke roughly filling the middle
    of the crop, well clear of the edges — stands in for a nicely written
    letter like "L"."""
    image = blank_crop(size)
    h, w = size
    cv2.line(image, (w // 4, h // 5), (w // 4, h - h // 5), 255, stroke_thickness)
    cv2.line(image, (w // 4, h - h // 5), (3 * w // 4, h - h // 5), 255, stroke_thickness)
    return image


def sparse_dot_crop(size: tuple[int, int] = (60, 60)) -> np.ndarray:
    """A tiny fleck of ink — far too little foreground to be a real glyph."""
    image = blank_crop(size)
    cv2.circle(image, (size[1] // 2, size[0] // 2), 1, 255, -1)
    return image


def noisy_crop(size: tuple[int, int] = (60, 60), seed: int = 0) -> np.ndarray:
    """Random ink covering most of the crop — stands in for scribble/noise
    rather than a legible character."""
    rng = np.random.default_rng(seed)
    return (rng.random(size) < 0.85).astype(np.uint8) * 255


def boundary_touching_crop(size: tuple[int, int] = (60, 60)) -> np.ndarray:
    """A stroke that runs right up to (and touches) the crop's edge."""
    image = blank_crop(size)
    cv2.rectangle(image, (0, size[0] // 3), (size[1] // 2, 2 * size[0] // 3), 255, -1)
    return image


def two_dot_crop(size: tuple[int, int] = (60, 60)) -> np.ndarray:
    """Two separate ink blobs — legitimate for characters like ':' but an
    unexpected split for most others."""
    image = blank_crop(size)
    cv2.circle(image, (size[1] // 2, size[0] // 3), 5, 255, -1)
    cv2.circle(image, (size[1] // 2, 2 * size[0] // 3), 5, 255, -1)
    return image
