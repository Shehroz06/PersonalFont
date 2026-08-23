"""Regression coverage for two real bugs found by manually reviewing the
printed template against real scans, not by a test:

1. The printed character box's outline must not survive thresholding, or
   it contaminates validation two ways — an empty box reads as a "valid"
   single-stroke glyph (the border alone looks like one), and a
   genuinely well-written character gets rejected as having "too many
   strokes" (the border becomes a second connected component alongside
   the real ink). Fixed by drawing the border in a light grey that
   disappears under thresholding, same idea as the guide glyph below.

2. An earlier template version also drew a large light-grey guide glyph
   inside the box, for the writer to trace over. That survived
   thresholding on a *real* phone scan (Adobe Scan, iOS) even though it
   reliably vanished on a directly-rendered PDF — scanning apps apply
   their own contrast/sharpening enhancement before we ever see the
   image, which can re-darken a light grey value we picked assuming a
   clean, unprocessed source. It was removed entirely rather than
   re-tuned to a different grey, since no fixed grey value can be
   guaranteed safe against arbitrary third-party image processing we
   don't control (see pdf_renderer.py's _BOX_STROKE_COLOR comment for
   the full account, including the 53/56-characters-failed evidence).
   There is nothing left to test for the guide glyph specifically — this
   file's job now is to make sure it doesn't quietly come back.

Builds the same scene (box outline only, optionally with handwriting
drawn on top) that the real template PDF now produces, using the actual
border color from pdf_renderer.py, then runs it through the real
preprocessing/validation code — without depending on an external PDF
rasterizer (poppler) in the automated suite; that tool was only ever used
for manual, one-off visual checks elsewhere in this project.

Otsu thresholding (pipeline.preprocessing.thresholding) picks a *global*
threshold from the whole page's histogram, not the crop in isolation —
Phase 3 thresholds the full aligned page before any cropping happens.
That matters here: a light grey border only reliably vanishes if the
page's histogram has genuinely dark content to anchor Otsu's threshold
low. Verified directly: an isolated box on an otherwise blank canvas does
*not* reproduce the real behavior (there's nothing dark to anchor
against), but adding a handful of realistic ArUco-marker-sized dark
squares — which every real template page always has, in all four corners
— does. The synthetic scene below includes those markers for that reason,
not as arbitrary decoration, and — matching the real pipeline's own
threshold-whole-page-then-crop-the-box order — thresholds the whole
scene before cropping to the box region for validation.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.template_gen.pdf_renderer import _BOX_STROKE_COLOR
from pipeline.preprocessing.grayscale import to_grayscale
from pipeline.preprocessing.noise_removal import remove_noise
from pipeline.preprocessing.thresholding import binarize_otsu
from pipeline.validation.validate import validate_glyph

CANVAS_SIZE = (1000, 800)  # (height, width) — large enough for realistic marker proportions
MARKER_SIZE_PX = 60

BOX_X0, BOX_Y0 = CANVAS_SIZE[1] // 2 - 130, CANVAS_SIZE[0] // 2 - 150
BOX_X1, BOX_Y1 = BOX_X0 + 260, BOX_Y0 + 300
CROP_PADDING = 6  # matches pipeline.segmentation.config.SegmentationConfig default


def _hex_to_bgr(hex_color) -> tuple[int, int, int]:
    return (round(hex_color.blue * 255), round(hex_color.green * 255), round(hex_color.red * 255))


def _draw_corner_markers(canvas: np.ndarray) -> None:
    """Stand-ins for the real ArUco markers every template page has —
    not decoded by anything here, just realistically dark and sized, so
    Otsu's global threshold lands where it would on a real page."""
    h, w = canvas.shape[:2]
    margin = 40
    for mx, my in (
        (margin, margin),
        (w - margin - MARKER_SIZE_PX, margin),
        (margin, h - margin - MARKER_SIZE_PX),
        (w - margin - MARKER_SIZE_PX, h - margin - MARKER_SIZE_PX),
    ):
        canvas[my : my + MARKER_SIZE_PX, mx : mx + MARKER_SIZE_PX] = 0


def _render_page_scene(with_handwriting: bool) -> np.ndarray:
    canvas = np.full((*CANVAS_SIZE, 3), 255, dtype=np.uint8)
    _draw_corner_markers(canvas)

    cv2.rectangle(canvas, (BOX_X0, BOX_Y0), (BOX_X1, BOX_Y1), _hex_to_bgr(_BOX_STROKE_COLOR), 1)
    # Deliberately no guide glyph drawn inside the box — see module
    # docstring, bug 2.

    if with_handwriting:
        ink = (30, 30, 30)
        mid_x = BOX_X0 + (BOX_X1 - BOX_X0) // 2
        cv2.line(canvas, (mid_x - 20, BOX_Y0 + 20), (BOX_X0 + 20, BOX_Y1 - 20), ink, 5)
        cv2.line(canvas, (mid_x - 20, BOX_Y0 + 20), (BOX_X1 - 20, BOX_Y1 - 20), ink, 5)
        cv2.line(canvas, (BOX_X0 + 40, BOX_Y1 - 60), (BOX_X1 - 40, BOX_Y1 - 60), ink, 5)

    return canvas


def _threshold_and_crop_box(with_handwriting: bool) -> np.ndarray:
    scene = _render_page_scene(with_handwriting)
    gray = to_grayscale(scene)
    denoised = remove_noise(gray)
    binary_page = binarize_otsu(denoised)

    return binary_page[
        BOX_Y0 - CROP_PADDING : BOX_Y1 + CROP_PADDING,
        BOX_X0 - CROP_PADDING : BOX_X1 + CROP_PADDING,
    ]


def test_empty_box_outline_does_not_survive_thresholding():
    crop = _threshold_and_crop_box(with_handwriting=False)

    assert crop.max() == 0, "the box border left ink behind on an unwritten box"


def test_empty_box_is_correctly_flagged_invalid():
    crop = _threshold_and_crop_box(with_handwriting=False)

    result = validate_glyph(crop, "A", "uppercase_A")

    assert result.valid is False
    assert any("Empty glyph" in warning for warning in result.warnings)


def test_handwritten_box_validates_without_border_contamination():
    crop = _threshold_and_crop_box(with_handwriting=True)

    result = validate_glyph(crop, "A", "uppercase_A")

    assert result.valid is True
    assert result.warnings == []
