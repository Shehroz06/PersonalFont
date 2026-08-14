"""Converts one glyph's SVG path data (Phase 8 output) into font outlines
— a TrueType (quadratic) glyph for the TTF, and a CFF charstring
(cubic) for the OTF — plus the per-glyph metrics (advance width, left
side bearing) spec §11 requires.

Coordinate system: the SVG path is in the same top-left-origin, y-down
pixel space Phase 7 normalized every glyph into (see
pipeline.normalization). Font em-space is baseline-origin, y-up. A single
fontTools Transform does both the y-flip and the "bitmap row baseline_px
maps to font y=0" translation, applied via TransformPen rather than by
hand-editing coordinates — verified empirically (see docs/architecture.md
Phase 9 notes) against a real rendered glyph, including one with a hole,
to confirm winding survives the SVG-evenodd -> TrueType-nonzero
conversion correctly.
"""

from __future__ import annotations

from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.svgLib.path import parse_path

from pipeline.font_generation.config import FontGenerationConfig
from pipeline.font_generation.errors import FontGenerationError

# Max on-curve error (in font units) permitted when converting cubic
# Bezier curves to TrueType's quadratic ones. Small relative to a 500-unit
# em — visually indistinguishable, per spec §10/§9's "preserve shape"
# requirements carrying through into the compiled font.
_CUBIC_TO_QUADRATIC_MAX_ERROR = 1.0


def _baseline_transform(baseline_px: float, x_shift: float = 0.0) -> Transform:
    return Transform(1, 0, 0, -1, x_shift, baseline_px)


def compute_ink_bounds(svg_path_data: str, config: FontGenerationConfig) -> tuple[float, float, float, float]:
    """(xMin, yMin, xMax, yMax) of the glyph's ink, in baseline-relative
    font units (before the per-glyph left-bearing shift)."""
    bounds_pen = BoundsPen(glyphSet=None)
    parse_path(svg_path_data, TransformPen(bounds_pen, _baseline_transform(config.baseline_px)))
    if bounds_pen.bounds is None:
        raise FontGenerationError("Glyph path produced no ink bounds (empty outline).")
    return bounds_pen.bounds


def compute_advance_and_transform(
    svg_path_data: str,
    config: FontGenerationConfig,
) -> tuple[Transform, int, float]:
    """(transform, advance_width, left_side_bearing) for one glyph.

    The transform repositions the glyph so its own ink starts at
    x=left_side_bearing, rather than wherever Phase 7 happened to
    horizontally center it within the shared normalization canvas — this
    is what gives each glyph its own proportional advance width (a narrow
    "i" advances less than a wide "W") instead of a fixed, monospace-style
    one, directly using the per-glyph "advance width"/"side bearings"
    metrics spec §11 asks for.
    """
    x_min, _y_min, x_max, _y_max = compute_ink_bounds(svg_path_data, config)
    ink_width = x_max - x_min
    left_bearing = config.side_bearing_units
    shift_x = left_bearing - x_min
    advance_width = round(ink_width + 2 * config.side_bearing_units)
    return _baseline_transform(config.baseline_px, shift_x), advance_width, left_bearing


def build_tt_glyph(svg_path_data: str, transform: Transform):
    tt_pen = TTGlyphPen(glyphSet=None)
    cu2qu_pen = Cu2QuPen(tt_pen, max_err=_CUBIC_TO_QUADRATIC_MAX_ERROR, reverse_direction=True)
    parse_path(svg_path_data, TransformPen(cu2qu_pen, transform))
    return tt_pen.glyph()


def build_cff_charstring(svg_path_data: str, transform: Transform, advance_width: int):
    t2_pen = T2CharStringPen(advance_width, glyphSet=None)
    parse_path(svg_path_data, TransformPen(t2_pen, transform))
    return t2_pen.getCharString()


def _notdef_box_points(config: FontGenerationConfig) -> list[tuple[float, float]]:
    margin = config.notdef_margin_units
    right = config.units_per_em - margin
    top = config.ascender
    bottom = 0.0
    return [(margin, bottom), (right, bottom), (right, top), (margin, top)]


def build_notdef_tt_glyph(config: FontGenerationConfig):
    pen = TTGlyphPen(glyphSet=None)
    points = _notdef_box_points(config)
    pen.moveTo(points[0])
    for point in points[1:]:
        pen.lineTo(point)
    pen.closePath()
    return pen.glyph()


def build_notdef_cff_charstring(config: FontGenerationConfig):
    pen = T2CharStringPen(config.units_per_em, glyphSet=None)
    points = _notdef_box_points(config)
    pen.moveTo(points[0])
    for point in points[1:]:
        pen.lineTo(point)
    pen.closePath()
    return pen.getCharString()
