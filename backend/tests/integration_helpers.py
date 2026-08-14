"""Builds a synthetic photograph of a real template page — real ArUco
markers plus simple hand-drawn-style ink, at true template box positions,
in standard scan polarity (white paper, black ink) — for the required
spec §19 integration test to run through *actual* Phase 3 preprocessing
(page detection, perspective correction, thresholding, deskew), not a
pre-binarized shortcut. Not a test module itself (no test_ prefix) —
pytest won't collect it.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.template_gen.coordinates import element_box_px, marker_corners_px, page_size_px
from app.template_gen.layout import ARUCO_DICTIONARY
from app.template_gen.schema import TemplateDocument, TemplatePage


def _draw_letter(canvas: np.ndarray, cx: int, cy: int, w: int, h: int, letter: str, thickness: int = 6) -> None:
    color = (0, 0, 0)
    if letter == "H":
        cv2.line(canvas, (cx - w // 3, cy - h // 3), (cx - w // 3, cy + h // 3), color, thickness)
        cv2.line(canvas, (cx + w // 3, cy - h // 3), (cx + w // 3, cy + h // 3), color, thickness)
        cv2.line(canvas, (cx - w // 3, cy), (cx + w // 3, cy), color, thickness)
    elif letter == "I":
        cv2.line(canvas, (cx, cy - h // 3), (cx, cy + h // 3), color, thickness)
    elif letter == "T":
        cv2.line(canvas, (cx - w // 3, cy - h // 3), (cx + w // 3, cy - h // 3), color, thickness)
        cv2.line(canvas, (cx, cy - h // 3), (cx, cy + h // 3), color, thickness)
    elif letter in ("O", "o"):
        cv2.ellipse(canvas, (cx, cy), (w // 3, h // 3), 0, 0, 360, color, thickness)
    elif letter == "L":
        cv2.line(canvas, (cx - w // 3, cy - h // 3), (cx - w // 3, cy + h // 3), color, thickness)
        cv2.line(canvas, (cx - w // 3, cy + h // 3), (cx + w // 3, cy + h // 3), color, thickness)
    else:
        cv2.line(canvas, (cx - w // 4, cy - h // 4), (cx + w // 4, cy + h // 4), color, thickness)
        cv2.line(canvas, (cx + w // 4, cy - h // 4), (cx - w // 4, cy + h // 4), color, thickness)


def render_clean_template_page(
    document: TemplateDocument,
    page: TemplatePage,
    dpi: float,
    characters_to_draw: set[str],
) -> np.ndarray:
    """A clean, standard-polarity (white paper, black ink) rendering of
    one template page: real ArUco markers plus simple strokes for the
    requested characters, at their true box positions."""
    width, height = page_size_px(document.page_size.width, document.page_size.height, dpi)
    canvas = np.full((height, width, 3), 255, dtype=np.uint8)

    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY)
    for marker in page.markers:
        corners = marker_corners_px(marker, document.page_size.height, dpi)
        x0, y0 = corners[0]
        size = int(round(corners[1][0] - corners[0][0]))
        marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker.marker_id, size)
        xi, yi = int(round(x0)), int(round(y0))
        canvas[yi : yi + size, xi : xi + size] = cv2.cvtColor(marker_img, cv2.COLOR_GRAY2BGR)

    for element in page.elements:
        if element.character not in characters_to_draw:
            continue
        x, y, w, h = element_box_px(element, document.page_size.height, dpi)
        cx, cy = int(x + w / 2), int(y + h / 2)
        _draw_letter(canvas, cx, cy, int(w), int(h), element.character)

    return canvas


def simulate_page_photo(
    clean_page: np.ndarray,
    canvas_size: tuple[int, int],
    angle_deg: float = 3.0,
    translation: tuple[float, float] = (30.0, 25.0),
    seed: int = 0,
) -> np.ndarray:
    """Embed ``clean_page`` into a larger noisy background at a slight
    rotation/translation — a phone photo of a printed page lying on a
    contrasting surface, which real Phase 3 page detection can find."""
    rng = np.random.default_rng(seed)
    canvas_w, canvas_h = canvas_size
    background = rng.integers(0, 80, size=(canvas_h, canvas_w, 3), dtype=np.uint8)

    page_h, page_w = clean_page.shape[:2]
    center = (page_w / 2, page_h / 2)
    matrix = cv2.getRotationMatrix2D(center, angle_deg, 1.0)
    matrix[0, 2] += translation[0] + (canvas_w - page_w) / 2
    matrix[1, 2] += translation[1] + (canvas_h - page_h) / 2

    warped = cv2.warpAffine(clean_page, matrix, (canvas_w, canvas_h), borderValue=(0, 0, 0))
    mask = cv2.warpAffine(
        np.full((page_h, page_w), 255, dtype=np.uint8), matrix, (canvas_w, canvas_h), borderValue=0
    )
    composite = np.where(mask[..., None] > 0, warped, background)
    return composite.astype(np.uint8)
