"""Stage 8 (spec §10): trace each normalized glyph bitmap into an SVG
path using potrace — an established, published tracing algorithm (via the
pure-Python `potracer` package), per Project_spec.txt's explicit guidance
to use a proven bitmap-to-vector approach rather than writing a Bezier
tracing algorithm from scratch.

Kept deliberately separate from font generation (Phase 9), per spec §10 —
this module only knows about bitmaps and SVG, nothing about fonts.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import potrace

from pipeline.ink_geometry import ink_pixel_count
from pipeline.normalization.schema import NormalizedGlyph
from pipeline.vectorization.config import VectorizationConfig
from pipeline.vectorization.errors import VectorizationError
from pipeline.vectorization.schema import VectorizedGlyph


def _curve_to_path_data(curve, precision: int) -> str:
    def fmt(point) -> str:
        return f"{point.x:.{precision}f},{point.y:.{precision}f}"

    parts = [f"M{fmt(curve.start_point)}"]
    for segment in curve:
        if segment.is_corner:
            parts.append(f"L{fmt(segment.c)}")
            parts.append(f"L{fmt(segment.end_point)}")
        else:
            parts.append(f"C{fmt(segment.c1)} {fmt(segment.c2)} {fmt(segment.end_point)}")
    parts.append("Z")
    return " ".join(parts)


def bitmap_to_path_data(image: np.ndarray, config: VectorizationConfig | None = None) -> str:
    """Trace a binary (ink=255/background=0) glyph image into an SVG path
    `d` string — one "M ... Z" subpath per traced contour (an outer
    outline, plus one per hole, e.g. the counter of an "o" or "A").

    Raises VectorizationError if the image has no ink, or if potrace
    (unexpectedly) produces no contours from it.
    """
    config = config or VectorizationConfig()

    if ink_pixel_count(image) == 0:
        raise VectorizationError("Cannot vectorize an empty glyph: it has no ink content.")

    # potrace.Bitmap inverts whatever array it's given before tracing, so
    # pre-inverting here (image == 0) is what makes ink=255 pixels the
    # ones actually traced — verified empirically against potracer 0.0.4.
    bitmap = potrace.Bitmap(image == 0)
    path = bitmap.trace(
        turdsize=config.turdsize,
        turnpolicy=config.turnpolicy,
        alphamax=config.alphamax,
        opticurve=config.opticurve,
        opttolerance=config.opttolerance,
    )

    if len(path) == 0:
        raise VectorizationError("Vectorization produced no contours for this glyph.")

    return " ".join(_curve_to_path_data(curve, config.decimal_precision) for curve in path)


def glyph_to_svg(
    image: np.ndarray,
    config: VectorizationConfig | None = None,
) -> str:
    """A standalone SVG document for one glyph: transparent background
    (no background rect drawn), viewBox matching the source bitmap's
    pixel dimensions 1:1 (SVG's coordinate system is already top-left
    origin/y-down, same as the bitmap — no flip needed here), and a
    single filled path using the evenodd fill rule so holes (the counter
    of an "o", "A", "e", ...) render correctly.
    """
    height, width = image.shape[:2]
    path_data = bitmap_to_path_data(image, config)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">'
        f'<path d="{path_data}" fill="#000000" fill-rule="evenodd"/>'
        f"</svg>"
    )


def vectorize_glyphs(
    glyphs: list[NormalizedGlyph],
    output_dir: Path,
    config: VectorizationConfig | None = None,
) -> list[VectorizedGlyph]:
    """Trace every normalized glyph into its own SVG file under
    ``output_dir``. Every glyph here already passed validation and
    normalization, so a failure at this point (unreadable file, empty
    image) signals a system-level problem and raises VectorizationError
    rather than being silently skipped.
    """
    config = config or VectorizationConfig()
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[VectorizedGlyph] = []
    for glyph in glyphs:
        image = cv2.imread(glyph.image_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise VectorizationError(f"Could not read glyph image at {glyph.image_path!r} for vectorization.")

        svg_document = glyph_to_svg(image, config)

        output_path = output_dir / f"{glyph.character_id}.svg"
        output_path.write_text(svg_document, encoding="utf-8")

        results.append(
            VectorizedGlyph(character=glyph.character, character_id=glyph.character_id, svg_path=str(output_path))
        )

    return results
