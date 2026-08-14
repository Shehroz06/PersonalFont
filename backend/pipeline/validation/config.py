from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationConfig:
    # Foreground (ink) pixel ratio, as a fraction of the crop. Below
    # `fail_low` the box is treated as unwritten; above `fail_high` it's
    # treated as noise/scribble/ink bleed rather than a clean character.
    foreground_ratio_fail_low: float = 0.005
    foreground_ratio_ideal_low: float = 0.02
    foreground_ratio_ideal_high: float = 0.35
    foreground_ratio_fail_high: float = 0.6

    # Tight bounding box (in px) of the ink itself, not the crop. Below
    # `fail_below` the glyph is too small to be usable; at/above
    # `ideal_at_or_above` it's comfortably legible.
    glyph_dimension_fail_below_px: int = 6
    glyph_dimension_ideal_at_or_above_px: int = 14

    # How close (px) ink can get to the crop edge before it's flagged as
    # possibly cut off.
    boundary_margin_px: int = 2
    boundary_touch_score: float = 0.5

    # Below this aggregate confidence, the glyph is marked invalid.
    min_confidence: float = 0.5

    # A check scoring below this is worth surfacing as a warning; above
    # it, the imperfection still lowers confidence a little (nothing in a
    # photographed handwriting sample is ever a mathematically perfect
    # 1.0) but isn't a distinct problem worth naming.
    warning_score_threshold: float = 0.85
