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


def preprocess_page(image: np.ndarray, config: PreprocessingConfig | None = None) -> PreprocessingResult:
    """Run one uploaded page image through every preprocessing stage.

    Raises PageDetectionError or DeskewError (see errors.py) with an
    actionable message if a stage cannot proceed; it never silently
    produces a garbage result.
    """
    config = config or PreprocessingConfig()

    page_corners = detect_page_contour(image, min_area_ratio=config.min_page_area_ratio)
    rectified = correct_perspective(image, page_corners, config.output_size_px)
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
    )
