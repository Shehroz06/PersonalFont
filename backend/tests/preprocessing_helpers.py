"""Synthetic-image builders shared by the preprocessing tests.

Not a test module itself (no test_ prefix) — pytest won't collect it.
"""

from __future__ import annotations

import cv2
import numpy as np

from pipeline.preprocessing.geometry import order_points


def rotated_rect_corners(
    center: tuple[float, float],
    width: float,
    height: float,
    angle_deg: float,
) -> np.ndarray:
    """Corners of a width x height rectangle centered at ``center`` and
    rotated by ``angle_deg`` (clockwise, degrees), ordered (tl, tr, br, bl)."""
    cx, cy = center
    half_w, half_h = width / 2, height / 2
    local = np.array(
        [
            [-half_w, -half_h],
            [half_w, -half_h],
            [half_w, half_h],
            [-half_w, half_h],
        ],
        dtype=np.float32,
    )
    theta = np.radians(angle_deg)
    rotation = np.array(
        [[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]],
        dtype=np.float32,
    )
    rotated = local @ rotation.T
    rotated[:, 0] += cx
    rotated[:, 1] += cy
    return order_points(rotated)


def build_synthetic_photo(
    canvas_size: tuple[int, int] = (600, 800),
    page_size: tuple[float, float] = (300, 500),
    angle_deg: float = 8.0,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """A noisy background with a bright, slightly-rotated rectangular
    "page" on it — stands in for a phone photo of a sheet of paper.

    Returns (image_bgr, page_corners_tl_tr_br_bl).
    """
    rng = np.random.default_rng(seed)
    height, width = canvas_size

    background = rng.integers(0, 80, size=(height, width, 3), dtype=np.uint8)

    center = (width / 2, height / 2)
    corners = rotated_rect_corners(center, page_size[0], page_size[1], angle_deg)

    image = background.copy()
    cv2.fillConvexPoly(image, corners.astype(np.int32), (255, 255, 255))

    return image, corners


def draw_ink_strokes(image: np.ndarray, corners: np.ndarray, seed: int = 0) -> np.ndarray:
    """Draw a few dark lines inside the quadrilateral defined by ``corners``,
    standing in for handwriting ink so thresholding/deskew have content to
    work with."""
    rng = np.random.default_rng(seed)
    out = image.copy()
    min_xy = corners.min(axis=0)
    max_xy = corners.max(axis=0)

    for _ in range(6):
        x1 = rng.uniform(min_xy[0] + 10, max_xy[0] - 10)
        y1 = rng.uniform(min_xy[1] + 10, max_xy[1] - 10)
        x2 = x1 + rng.uniform(-40, 40)
        y2 = y1 + rng.uniform(10, 40)
        cv2.line(out, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 0), 4)

    return out
