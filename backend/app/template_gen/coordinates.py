"""Converts template geometry from PDF point units (origin bottom-left, y
up — the coordinate system template_v1.json and layout.py use) into pixel
units (origin top-left, y down — the coordinate system numpy/OpenCV images
use, at a caller-chosen working DPI).

Every stage that needs to relate a rectified/aligned image back to
template coordinates (alignment now, segmentation/character-extraction
next) must go through here rather than re-deriving the y-flip itself.
"""

from __future__ import annotations

import numpy as np

from app.template_gen.layout import POINTS_PER_INCH
from app.template_gen.schema import TemplateElement, TemplateMarker


def pt_to_px_scale(dpi: float) -> float:
    return dpi / POINTS_PER_INCH


def page_size_px(width_pt: float, height_pt: float, dpi: float) -> tuple[int, int]:
    scale = pt_to_px_scale(dpi)
    return round(width_pt * scale), round(height_pt * scale)


def box_pt_to_px(
    x_pt: float,
    y_pt: float,
    width_pt: float,
    height_pt: float,
    page_height_pt: float,
    dpi: float,
) -> tuple[float, float, float, float]:
    """Convert a (x, y, width, height) box — y measured up from the page
    bottom, as in template_v1.json — to (x, y, width, height) in pixels
    with y measured down from the image top."""
    scale = pt_to_px_scale(dpi)
    x_px = x_pt * scale
    width_px = width_pt * scale
    height_px = height_pt * scale
    top_pt = y_pt + height_pt
    y_px = (page_height_pt - top_pt) * scale
    return x_px, y_px, width_px, height_px


def box_corners_px(
    x_pt: float,
    y_pt: float,
    width_pt: float,
    height_pt: float,
    page_height_pt: float,
    dpi: float,
) -> np.ndarray:
    """The box's 4 corners in pixel space, ordered (tl, tr, br, bl) —
    matching both pipeline.preprocessing.geometry.order_points and the
    corner order cv2.aruco.detectMarkers returns."""
    x_px, y_px, w_px, h_px = box_pt_to_px(x_pt, y_pt, width_pt, height_pt, page_height_pt, dpi)
    return np.array(
        [
            [x_px, y_px],
            [x_px + w_px, y_px],
            [x_px + w_px, y_px + h_px],
            [x_px, y_px + h_px],
        ],
        dtype=np.float32,
    )


def marker_corners_px(marker: TemplateMarker, page_height_pt: float, dpi: float) -> np.ndarray:
    return box_corners_px(marker.x, marker.y, marker.size, marker.size, page_height_pt, dpi)


def element_box_px(element: TemplateElement, page_height_pt: float, dpi: float) -> tuple[float, float, float, float]:
    return box_pt_to_px(element.x, element.y, element.width, element.height, page_height_pt, dpi)
