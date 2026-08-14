"""Builds real VectorizedGlyph fixtures (via the actual normalize ->
vectorize chain, not hand-crafted SVGs) for the font generation tests.
Not a test module itself (no test_ prefix) — pytest won't collect it.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from pipeline.normalization.normalize import normalize_glyph
from pipeline.vectorization.schema import VectorizedGlyph
from pipeline.vectorization.trace import glyph_to_svg
from tests.vectorization_helpers import filled_circle, letter_a_with_hole, letter_l_stroke


def make_vectorized_glyph(
    character: str,
    character_id: str,
    category: str,
    raw_image: np.ndarray,
    output_dir: Path,
) -> VectorizedGlyph:
    normalized = normalize_glyph(raw_image, character, category)
    svg = glyph_to_svg(normalized)
    output_dir.mkdir(parents=True, exist_ok=True)
    svg_path = output_dir / f"{character_id}.svg"
    svg_path.write_text(svg, encoding="utf-8")
    return VectorizedGlyph(character=character, character_id=character_id, svg_path=str(svg_path))


def build_sample_glyphs(output_dir: Path) -> list[VectorizedGlyph]:
    """"A" (has a genuine hole), "o" (wide, round), "L" (narrow, no
    hole) — enough variety to exercise hole winding, proportional
    advance widths, and plain outlines."""
    return [
        make_vectorized_glyph("A", "uppercase_A", "uppercase", letter_a_with_hole(), output_dir),
        make_vectorized_glyph("o", "lowercase_o", "lowercase", filled_circle(), output_dir),
        make_vectorized_glyph("L", "uppercase_L", "uppercase", letter_l_stroke(), output_dir),
    ]
