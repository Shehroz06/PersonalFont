import xml.etree.ElementTree as ET
from pathlib import Path

import cv2
import numpy as np
import pytest

from pipeline.normalization.schema import NormalizedGlyph
from pipeline.vectorization.config import VectorizationConfig
from pipeline.vectorization.errors import VectorizationError
from pipeline.vectorization.trace import bitmap_to_path_data, glyph_to_svg, vectorize_glyphs
from tests.vectorization_helpers import (
    filled_circle,
    iou,
    letter_a_with_hole,
    letter_l_stroke,
    rasterize_single_subpath,
)


# --- bitmap_to_path_data -----------------------------------------------


def test_bitmap_to_path_data_raises_on_empty_image():
    blank = np.zeros((100, 100), dtype=np.uint8)

    with pytest.raises(VectorizationError):
        bitmap_to_path_data(blank)


def test_bitmap_to_path_data_single_shape_has_one_subpath():
    path_data = bitmap_to_path_data(filled_circle())

    assert path_data.count("M") == 1
    assert path_data.strip().endswith("Z")


def test_bitmap_to_path_data_shape_with_hole_has_two_subpaths():
    path_data = bitmap_to_path_data(letter_a_with_hole())

    assert path_data.count("M") == 2


def test_bitmap_to_path_data_preserves_shape_closely():
    size = (500, 500)
    original = letter_l_stroke(size)

    path_data = bitmap_to_path_data(original)
    reconstructed = rasterize_single_subpath(path_data, size)

    assert iou(original, reconstructed) > 0.9


def test_opticurve_reduces_or_matches_node_count():
    image = filled_circle()

    optimized = bitmap_to_path_data(image, VectorizationConfig(opticurve=True))
    unoptimized = bitmap_to_path_data(image, VectorizationConfig(opticurve=False))

    def node_count(path_data: str) -> int:
        return path_data.count("L") + path_data.count("C")

    assert node_count(optimized) <= node_count(unoptimized)


# --- glyph_to_svg --------------------------------------------------------


def test_glyph_to_svg_is_well_formed_xml_with_transparent_background():
    svg = glyph_to_svg(letter_l_stroke())

    root = ET.fromstring(svg)  # raises if malformed
    tag = root.tag.split("}")[-1]
    assert tag == "svg"

    children = [child.tag.split("}")[-1] for child in root]
    assert "path" in children
    assert "rect" not in children  # no background fill drawn


def test_glyph_to_svg_viewbox_matches_source_dimensions():
    image = np.zeros((240, 180), dtype=np.uint8)
    cv2.circle(image, (90, 120), 60, 255, -1)

    svg = glyph_to_svg(image)

    assert 'viewBox="0 0 180 240"' in svg
    assert 'width="180"' in svg
    assert 'height="240"' in svg


def test_glyph_to_svg_raises_for_empty_glyph():
    with pytest.raises(VectorizationError):
        glyph_to_svg(np.zeros((50, 50), dtype=np.uint8))


# --- vectorize_glyphs (batch) ------------------------------------------


def _make_normalized_glyph(character: str, character_id: str, image_path: Path) -> NormalizedGlyph:
    return NormalizedGlyph(character=character, character_id=character_id, image_path=str(image_path))


def test_vectorize_glyphs_writes_one_svg_per_glyph(tmp_path: Path):
    a_path = tmp_path / "uppercase_A.png"
    o_path = tmp_path / "lowercase_o.png"
    cv2.imwrite(str(a_path), letter_a_with_hole())
    cv2.imwrite(str(o_path), filled_circle())

    glyphs = [
        _make_normalized_glyph("A", "uppercase_A", a_path),
        _make_normalized_glyph("o", "lowercase_o", o_path),
    ]

    output_dir = tmp_path / "svg"
    results = vectorize_glyphs(glyphs, output_dir)

    assert {r.character_id for r in results} == {"uppercase_A", "lowercase_o"}
    for result in results:
        svg_path = Path(result.svg_path)
        assert svg_path.exists()
        assert svg_path.parent == output_dir
        assert "<path" in svg_path.read_text()


def test_vectorize_glyphs_raises_for_unreadable_image(tmp_path: Path):
    glyphs = [_make_normalized_glyph("A", "uppercase_A", tmp_path / "missing.png")]

    with pytest.raises(VectorizationError):
        vectorize_glyphs(glyphs, tmp_path / "svg")
