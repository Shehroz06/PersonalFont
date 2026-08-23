"""Orchestrates the preprocessing stages in order. Each stage is its own
independently-testable module (page_detection, perspective_correction,
crop, grayscale, noise_removal, thresholding, deskew) — this function only
chains them; it must not contain image-processing logic of its own.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from pipeline.preprocessing.config import PreprocessingConfig
from pipeline.preprocessing.crop import autocrop_borders
from pipeline.preprocessing.deskew import deskew
from pipeline.preprocessing.errors import PageDetectionError
from pipeline.preprocessing.grayscale import to_grayscale
from pipeline.preprocessing.noise_removal import remove_noise
from pipeline.preprocessing.page_detection import detect_page_contour
from pipeline.preprocessing.perspective_correction import correct_perspective
from pipeline.preprocessing.thresholding import binarize_adaptive, binarize_otsu


@dataclass(frozen=True)
class PreprocessingResult:
    page_corners: np.ndarray
    rectified: np.ndarray  # perspective-corrected + cropped, still color/gray
    grayscale: np.ndarray
    denoised: np.ndarray
    binary: np.ndarray  # ink=255 on background=0, see thresholding.py
    deskewed: np.ndarray
    skew_angle_deg: float
    page_detected: bool  # False if this stage fell back to "the image is already the page"


def _detect_and_rectify(image: np.ndarray, config: PreprocessingConfig) -> tuple[np.ndarray, np.ndarray, bool]:
    """Returns (page_corners, rectified_image, page_detected).

    Falls back to treating the whole input as an already-flat page when
    no page-sized quadrilateral can be found, rather than failing the
    page outright — the common cause is a photo that's already been
    perspective-corrected and tightly cropped by a phone scanning app
    (Adobe Scan, Google Drive scan, ...), which leaves no contrasting
    background for contour-based detection to find anything against.
    This is safe to fall back on: alignment (Phase 4) independently
    recovers the full rotation/perspective/scale correction from the
    page's ArUco markers regardless of whether this stage's own
    correction ran, so skipping it here doesn't skip correction overall
    — it just skips a redundant step when there's no boundary to find.
    """
    try:
        page_corners = detect_page_contour(image, min_area_ratio=config.min_page_area_ratio)
        rectified = correct_perspective(image, page_corners, config.output_size_px)
        return page_corners, rectified, True
    except PageDetectionError as exc:
        if to_grayscale(image).mean() < config.min_fallback_brightness:
            # Doesn't even look like a page (mostly dark/noisy) — the
            # original detection failure is the right, actionable error,
            # not a silent fallback onto obvious garbage.
            raise exc

        height, width = image.shape[:2]
        page_corners = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
        return page_corners, image, False


def preprocess_page(image: np.ndarray, config: PreprocessingConfig | None = None) -> PreprocessingResult:
    """Run one uploaded page image through every preprocessing stage.

    Raises DeskewError (see errors.py) with an actionable message if a
    stage cannot proceed; it never silently produces a garbage result.
    Page detection specifically degrades gracefully instead of raising —
    see _detect_and_rectify.
    """
    config = config or PreprocessingConfig()

    page_corners, rectified, page_detected = _detect_and_rectify(image, config)
    rectified = autocrop_borders(rectified)

    gray = to_grayscale(rectified)
    denoised = remove_noise(gray)

    if config.threshold_method == "adaptive":
        binary = binarize_adaptive(denoised)
    else:
        binary = binarize_otsu(denoised)

    deskewed, angle = deskew(binary)

    return PreprocessingResult(
        page_corners=page_corners,
        rectified=rectified,
        grayscale=gray,
        denoised=denoised,
        binary=binary,
        deskewed=deskewed,
        skew_angle_deg=angle,
        page_detected=page_detected,
    )
