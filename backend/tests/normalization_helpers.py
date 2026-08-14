"""Synthetic glyph crops for the normalization tests.

Built directly in the ink=255/background=0 convention. Not a test module
itself (no test_ prefix) — pytest won't collect it.
"""

from __future__ import annotations

import numpy as np


def stroke_crop(
    content_size: tuple[int, int],
    canvas_size: tuple[int, int] = (140, 140),
    offset: tuple[int, int] = (25, 15),
) -> np.ndarray:
    """A filled rectangle of ``content_size`` (width, height), placed at
    ``offset`` within a larger blank ``canvas_size`` crop — stands in for
    a raw extracted glyph crop (padding around the actual ink)."""
    content_w, content_h = content_size
    canvas_w, canvas_h = canvas_size
    image = np.zeros((canvas_h, canvas_w), dtype=np.uint8)

    x0, y0 = offset
    image[y0 : y0 + content_h, x0 : x0 + content_w] = 255
    return image
