"""Individual validation checks (spec §8), each scoring a binary glyph
crop on a 0-1 scale rather than just pass/fail, so validate.py can combine
them into a graded confidence instead of a single boolean.

Expects the ink=255 / background=0 convention established in
pipeline.preprocessing.thresholding — every check here assumes that, and
none re-derives or second-guesses it.
"""

from __future__ import annotations

import cv2
import numpy as np

from pipeline.validation.config import ValidationConfig

# Characters whose correctly-written form is more than one connected ink
# component (a dot above a stem, two dots, two marks). Everything else in
# the V1 character set (see app.template_gen.character_set) is expected to
# be a single connected stroke — even a crossed "x" or "t", since the
# crossing strokes touch and merge into one component.
_MULTI_COMPONENT_CHARACTERS: dict[str, tuple[int, int]] = {
    "i": (1, 2),
    "j": (1, 2),
    ":": (1, 2),
    ";": (1, 2),
    '"': (1, 2),
}
_DEFAULT_COMPONENT_RANGE = (1, 1)


def expected_component_range(character: str) -> tuple[int, int]:
    return _MULTI_COMPONENT_CHARACTERS.get(character, _DEFAULT_COMPONENT_RANGE)


def _ramp_up_score(value: float, fail_below: float, ideal_at_or_above: float) -> float:
    """0 at/below fail_below, 1 at/above ideal_at_or_above, linear between."""
    if value <= fail_below:
        return 0.0
    if value >= ideal_at_or_above:
        return 1.0
    return (value - fail_below) / (ideal_at_or_above - fail_below)


def _trapezoidal_score(value: float, fail_low: float, ideal_low: float, ideal_high: float, fail_high: float) -> float:
    """0 at/beyond either fail bound, 1 across the ideal band, linear ramps between."""
    if value <= fail_low or value >= fail_high:
        return 0.0
    if value < ideal_low:
        return (value - fail_low) / (ideal_low - fail_low)
    if value > ideal_high:
        return (fail_high - value) / (fail_high - ideal_high)
    return 1.0


def ink_pixel_count(image: np.ndarray) -> int:
    return int(np.count_nonzero(image))


def ink_bounding_box(image: np.ndarray) -> tuple[int, int, int, int] | None:
    """Tight (x0, y0, x1, y1) bounding box of ink pixels, or None if empty."""
    coords = cv2.findNonZero(image)
    if coords is None:
        return None
    x, y, w, h = cv2.boundingRect(coords)
    return x, y, x + w, y + h


def check_foreground_ratio(image: np.ndarray, config: ValidationConfig) -> tuple[float, str | None]:
    ratio = ink_pixel_count(image) / image.size
    score = _trapezoidal_score(
        ratio,
        config.foreground_ratio_fail_low,
        config.foreground_ratio_ideal_low,
        config.foreground_ratio_ideal_high,
        config.foreground_ratio_fail_high,
    )
    if score >= 1.0:
        return score, None
    if ratio < config.foreground_ratio_ideal_low:
        return score, "Insufficient foreground pixels"
    return score, "Excessive noise"


def check_glyph_size(image: np.ndarray, config: ValidationConfig) -> tuple[float, str | None]:
    bbox = ink_bounding_box(image)
    if bbox is None:
        return 0.0, "Empty glyph"

    x0, y0, x1, y1 = bbox
    min_dimension = min(x1 - x0, y1 - y0)
    score = _ramp_up_score(
        min_dimension,
        config.glyph_dimension_fail_below_px,
        config.glyph_dimension_ideal_at_or_above_px,
    )
    warning = "Glyph is extremely small" if score < 1.0 else None
    return score, warning


def check_touches_boundary(image: np.ndarray, config: ValidationConfig) -> tuple[float, str | None]:
    bbox = ink_bounding_box(image)
    if bbox is None:
        return 1.0, None

    height, width = image.shape[:2]
    margin = config.boundary_margin_px
    x0, y0, x1, y1 = bbox
    touches = x0 <= margin or y0 <= margin or x1 >= width - margin or y1 >= height - margin

    if touches:
        return config.boundary_touch_score, "Glyph touches the crop boundary and may be cut off"
    return 1.0, None


def check_component_count(image: np.ndarray, character: str) -> tuple[float, str | None]:
    num_labels, _labels = cv2.connectedComponents(image, connectivity=8)
    count = num_labels - 1  # exclude the background label

    low, high = expected_component_range(character)
    if low <= count <= high:
        return 1.0, None

    distance = (low - count) if count < low else (count - high)
    score = max(0.0, 1.0 - 0.35 * distance)
    warning = "Unexpected number of disconnected strokes" if count != 0 else "Empty glyph"
    return score, warning
