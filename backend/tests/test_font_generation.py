from pathlib import Path

import numpy as np
import pytest
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

from pipeline.font_generation.build import NOTDEF_GLYPH_NAME, generate_fonts
from pipeline.font_generation.config import FontGenerationConfig, FontMetadata
from pipeline.font_generation.errors import FontGenerationError
from pipeline.vectorization.schema import VectorizedGlyph
from tests.font_generation_helpers import build_sample_glyphs


@pytest.fixture
def sample_glyphs(tmp_path: Path) -> list[VectorizedGlyph]:
    return build_sample_glyphs(tmp_path / "svg")


def test_generate_fonts_creates_loadable_ttf_and_otf(tmp_path: Path, sample_glyphs):
    result = generate_fonts(sample_glyphs, tmp_path / "font")

    ttf_path = Path(result.ttf_path)
    otf_path = Path(result.otf_path)
    assert ttf_path.exists() and ttf_path.stat().st_size > 0
    assert otf_path.exists() and otf_path.stat().st_size > 0
    assert result.glyph_count == 3

    TTFont(str(ttf_path)).close()  # raises if malformed
    TTFont(str(otf_path)).close()


def test_generate_fonts_includes_notdef_glyph(tmp_path: Path, sample_glyphs):
    result = generate_fonts(sample_glyphs, tmp_path / "font")

    font = TTFont(result.ttf_path)
    assert NOTDEF_GLYPH_NAME in font.getGlyphOrder()
    font.close()


def test_generate_fonts_cmap_maps_unicode_to_character_id(tmp_path: Path, sample_glyphs):
    result = generate_fonts(sample_glyphs, tmp_path / "font")

    font = TTFont(result.ttf_path)
    cmap = font.getBestCmap()
    assert cmap[ord("A")] == "uppercase_A"
    assert cmap[ord("o")] == "lowercase_o"
    assert cmap[ord("L")] == "uppercase_L"
    font.close()


def test_generate_fonts_default_family_name_is_personalfont(tmp_path: Path, sample_glyphs):
    result = generate_fonts(sample_glyphs, tmp_path / "font")

    assert result.family_name == "PersonalFont"
    font = TTFont(result.ttf_path)
    assert font["name"].getDebugName(1) == "PersonalFont"
    font.close()


def test_generate_fonts_accepts_custom_family_name(tmp_path: Path, sample_glyphs):
    metadata = FontMetadata(family_name="My Handwriting", version="2.3", creator="Jane Doe")

    result = generate_fonts(sample_glyphs, tmp_path / "font", metadata=metadata)

    assert result.family_name == "My Handwriting"
    font = TTFont(result.ttf_path)
    assert font["name"].getDebugName(1) == "My Handwriting"
    assert font["name"].getDebugName(5) == "2.3"  # version string record
    font.close()


def test_generate_fonts_glyphs_have_proportional_advance_widths(tmp_path: Path, sample_glyphs):
    result = generate_fonts(sample_glyphs, tmp_path / "font")

    font = TTFont(result.ttf_path)
    hmtx = font["hmtx"]
    widths = {name: hmtx[name][0] for name in ("uppercase_A", "lowercase_o", "uppercase_L")}
    font.close()

    assert all(width > 0 for width in widths.values())
    assert len(set(widths.values())) > 1  # not a fixed monospace-style advance


def test_generate_fonts_raises_for_empty_glyph_list(tmp_path: Path):
    with pytest.raises(FontGenerationError):
        generate_fonts([], tmp_path / "font")


def test_generate_fonts_raises_for_missing_svg_file(tmp_path: Path):
    glyphs = [VectorizedGlyph(character="A", character_id="uppercase_A", svg_path=str(tmp_path / "missing.svg"))]

    with pytest.raises(FontGenerationError):
        generate_fonts(glyphs, tmp_path / "font")


# --- rendering (actual functional verification, not just structural) ------


def _render_text(font_path: str, text: str, size: int = 200) -> np.ndarray:
    font = ImageFont.truetype(font_path, size)
    image = Image.new("L", (size * len(text) + 40, size + 60), 255)
    draw = ImageDraw.Draw(image)
    draw.text((20, 20), text, font=font, fill=0)
    return np.array(image)


def test_generated_ttf_renders_visible_glyphs(tmp_path: Path, sample_glyphs):
    result = generate_fonts(sample_glyphs, tmp_path / "font")

    rendered = _render_text(result.ttf_path, "AoL")

    assert rendered.min() < 50  # some dark (ink) pixels were actually drawn
    assert rendered.max() > 200  # and plenty of background remains


def test_generated_otf_renders_visible_glyphs(tmp_path: Path, sample_glyphs):
    result = generate_fonts(sample_glyphs, tmp_path / "font")

    rendered = _render_text(result.otf_path, "AoL")

    assert rendered.min() < 50
    assert rendered.max() > 200


def test_generated_font_preserves_hole_in_a(tmp_path: Path, sample_glyphs):
    """Specifically checks that the "A" glyph's triangular counter
    renders as background, not filled in — the real risk when converting
    SVG's evenodd-filled contours into TrueType's nonzero-winding ones."""
    result = generate_fonts(sample_glyphs, tmp_path / "font")

    font = ImageFont.truetype(result.ttf_path, 400)
    image = Image.new("L", (400, 500), 255)
    draw = ImageDraw.Draw(image)
    draw.text((0, 0), "A", font=font, fill=0)
    pixels = np.array(image)

    bbox = font.getbbox("A")
    x0, y0, x1, y1 = bbox
    center_x = (x0 + x1) // 2
    # Sample just above the crossbar, inside where the triangular counter
    # should be — well within the glyph's bounds but not on any stroke.
    counter_y = y0 + int((y1 - y0) * 0.35)

    assert pixels[counter_y, center_x] > 200  # background, i.e. the hole survived
