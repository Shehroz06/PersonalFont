"""Synthetic template/photo builders shared by the alignment tests.

Not a test module itself (no test_ prefix) — pytest won't collect it.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.template_gen.coordinates import marker_corners_px, page_size_px
from app.template_gen.layout import ARUCO_DICTIONARY, MARKER_CORNERS
from app.template_gen.schema import PageSize, TemplateDocument, TemplateMarker, TemplatePage

PAGE_WIDTH_PT = 300.0
PAGE_HEIGHT_PT = 400.0
MARGIN_PT = 20.0
MARKER_SIZE_PT = 30.0


def markers_for_page(page_index: int) -> list[TemplateMarker]:
    m = MARKER_SIZE_PT
    positions = {
        "top_left": (MARGIN_PT, PAGE_HEIGHT_PT - MARGIN_PT - m),
        "top_right": (PAGE_WIDTH_PT - MARGIN_PT - m, PAGE_HEIGHT_PT - MARGIN_PT - m),
        "bottom_left": (MARGIN_PT, MARGIN_PT),
        "bottom_right": (PAGE_WIDTH_PT - MARGIN_PT - m, MARGIN_PT),
    }
    markers = []
    for corner_index, corner in enumerate(MARKER_CORNERS):
        x, y = positions[corner]
        markers.append(
            TemplateMarker(
                marker_id=page_index * len(MARKER_CORNERS) + corner_index,
                corner=corner,
                x=x,
                y=y,
                size=m,
            )
        )
    return markers


def build_minimal_template_document(num_pages: int, template_id: str = "template_test") -> TemplateDocument:
    """A template with no character elements, just alignment markers —
    enough for alignment tests without dragging in the full character set."""
    pages = [
        TemplatePage(page=page_index + 1, elements=[], markers=markers_for_page(page_index))
        for page_index in range(num_pages)
    ]
    return TemplateDocument(
        template_version="1.0",
        template_id=template_id,
        page_size=PageSize(width=PAGE_WIDTH_PT, height=PAGE_HEIGHT_PT),
        character_count=0,
        pages=pages,
    )


def render_template_page_image(document: TemplateDocument, page: TemplatePage, dpi: float) -> np.ndarray:
    """A clean grayscale rendering of just page's ArUco markers, standing
    in for a flatbed-scan-quality print of that template page."""
    width, height = page_size_px(document.page_size.width, document.page_size.height, dpi)
    canvas = np.full((height, width), 255, dtype=np.uint8)

    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY)
    for marker in page.markers:
        corners = marker_corners_px(marker, document.page_size.height, dpi)
        x0, y0 = corners[0]
        size = int(round(corners[1][0] - corners[0][0]))
        marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker.marker_id, size)
        yi, xi = int(round(y0)), int(round(x0))
        canvas[yi : yi + size, xi : xi + size] = marker_img

    return canvas


def simulate_photo(
    template_image: np.ndarray,
    canvas_size: tuple[int, int],
    angle_deg: float = 0.0,
    scale: float = 1.0,
    translation: tuple[float, float] = (0.0, 0.0),
) -> np.ndarray:
    """Place a rotated/scaled/translated copy of ``template_image`` onto a
    ``canvas_size`` (width, height) grayscale canvas — stands in for a
    phone photo of the printed page taken at an angle."""
    height, width = template_image.shape[:2]
    center = (width / 2, height / 2)
    matrix = cv2.getRotationMatrix2D(center, angle_deg, scale)
    matrix[0, 2] += translation[0]
    matrix[1, 2] += translation[1]

    canvas_w, canvas_h = canvas_size
    return cv2.warpAffine(template_image, matrix, (canvas_w, canvas_h), borderValue=200)


def blank_out_region(image: np.ndarray, corners_px: np.ndarray) -> np.ndarray:
    """Paint over the area covered by ``corners_px`` (as returned by
    marker_corners_px) with mid-gray, simulating a marker that a photo
    failed to capture (folded corner, glare, out of frame, ...)."""
    out = image.copy()
    x0, y0 = corners_px.min(axis=0).astype(int)
    x1, y1 = corners_px.max(axis=0).astype(int)
    out[y0:y1, x0:x1] = 128
    return out
