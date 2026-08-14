from pathlib import Path

import cv2
import numpy as np
import pytest

from pipeline.ink_geometry import ink_bounding_box
from pipeline.normalization.config import NormalizationConfig
from pipeline.normalization.errors import NormalizationError
from pipeline.normalization.normalize import normalize_glyph, normalize_glyphs
from pipeline.segmentation.schema import ExtractedGlyph, GlyphCropBox
from pipeline.validation.schema import ValidationResult
from tests.normalization_helpers import stroke_crop

CONFIG = NormalizationConfig()


def test_normalize_glyph_output_matches_canvas_size():
    result = normalize_glyph(stroke_crop((30, 30)), "A", "uppercase")

    assert result.shape == (CONFIG.canvas_height, CONFIG.canvas_width)


def test_normalize_glyph_preserves_aspect_ratio():
    result = normalize_glyph(stroke_crop((60, 20)), "A", "uppercase")

    bbox = ink_bounding_box(result)
    assert bbox is not None
    x0, y0, x1, y1 = bbox
    width, height = x1 - x0, y1 - y0

    assert width / height == pytest.approx(60 / 20, rel=0.05)


def test_normalize_glyph_tall_category_is_taller_than_short():
    tall_result = normalize_glyph(stroke_crop((30, 30)), "A", "uppercase")
    short_result = normalize_glyph(stroke_crop((30, 30)), "a", "lowercase")

    tall_bbox = ink_bounding_box(tall_result)
    short_bbox = ink_bounding_box(short_result)

    tall_height = tall_bbox[3] - tall_bbox[1]
    short_height = short_bbox[3] - short_bbox[1]

    assert tall_height > short_height


def test_normalize_glyph_ascender_lowercase_matches_tall_height():
    tall_upper = normalize_glyph(stroke_crop((30, 30)), "A", "uppercase")
    ascender_lower = normalize_glyph(stroke_crop((30, 30)), "b", "lowercase")  # 'b' is an ascender

    upper_bbox = ink_bounding_box(tall_upper)
    lower_bbox = ink_bounding_box(ascender_lower)

    assert (upper_bbox[3] - upper_bbox[1]) == (lower_bbox[3] - lower_bbox[1])


def test_normalize_glyph_non_descender_bottom_aligns_to_baseline():
    result = normalize_glyph(stroke_crop((30, 30)), "a", "lowercase")

    bbox = ink_bounding_box(result)
    baseline_y = round(CONFIG.baseline_ratio * CONFIG.canvas_height)

    assert bbox[3] == pytest.approx(baseline_y, abs=2)


def test_normalize_glyph_descender_extends_below_baseline():
    result = normalize_glyph(stroke_crop((30, 30)), "g", "lowercase")

    bbox = ink_bounding_box(result)
    baseline_y = round(CONFIG.baseline_ratio * CONFIG.canvas_height)

    assert bbox[3] > baseline_y + 5


def test_normalize_glyph_is_horizontally_centered():
    # off-center content within its source crop shouldn't matter — only
    # the ink's own shape does.
    result = normalize_glyph(stroke_crop((30, 30), canvas_size=(200, 140), offset=(5, 15)), "A", "uppercase")

    bbox = ink_bounding_box(result)
    center_x = (bbox[0] + bbox[2]) / 2

    assert center_x == pytest.approx(CONFIG.canvas_width / 2, abs=2)


def test_normalize_glyph_raises_on_empty_image():
    blank = np.zeros((100, 100), dtype=np.uint8)

    with pytest.raises(NormalizationError):
        normalize_glyph(blank, "A", "uppercase")


def test_normalize_glyph_output_stays_binary():
    result = normalize_glyph(stroke_crop((17, 23)), "A", "uppercase")  # awkward size forces resampling

    assert set(np.unique(result)).issubset({0, 255})


# --- normalize_glyphs (batch) -----------------------------------------------


def _make_glyph(character: str, character_id: str, image_path: Path) -> ExtractedGlyph:
    return ExtractedGlyph(
        job_id="testjob",
        page=1,
        character=character,
        character_id=character_id,
        source_image="page_1.png",
        crop_box=GlyphCropBox(x=0, y=0, width=140, height=140),
        extraction_confidence=1.0,
        image_path=str(image_path),
    )


def _make_validation(character_id: str, valid: bool) -> ValidationResult:
    return ValidationResult(
        character=character_id[-1],
        character_id=character_id,
        valid=valid,
        confidence=1.0 if valid else 0.0,
        warnings=[] if valid else ["Empty glyph"],
    )


def test_normalize_glyphs_only_processes_valid_glyphs(tmp_path: Path):
    a_path = tmp_path / "uppercase_A.png"
    b_path = tmp_path / "uppercase_B.png"
    cv2.imwrite(str(a_path), stroke_crop((30, 30)))
    cv2.imwrite(str(b_path), stroke_crop((30, 30)))

    glyphs = [_make_glyph("A", "uppercase_A", a_path), _make_glyph("B", "uppercase_B", b_path)]
    validations = [_make_validation("uppercase_A", True), _make_validation("uppercase_B", False)]

    output_dir = tmp_path / "normalized"
    results = normalize_glyphs(glyphs, validations, output_dir)

    assert [r.character_id for r in results] == ["uppercase_A"]
    assert (output_dir / "uppercase_A.png").exists()
    assert not (output_dir / "uppercase_B.png").exists()


def test_normalize_glyphs_raises_for_unknown_character_id(tmp_path: Path):
    path = tmp_path / "mystery.png"
    cv2.imwrite(str(path), stroke_crop((30, 30)))

    glyphs = [_make_glyph("A", "not_a_real_character_id", path)]
    validations = [_make_validation("not_a_real_character_id", True)]

    with pytest.raises(NormalizationError):
        normalize_glyphs(glyphs, validations, tmp_path / "out")


def test_normalize_glyphs_raises_for_unreadable_image(tmp_path: Path):
    missing_path = tmp_path / "does_not_exist.png"

    glyphs = [_make_glyph("A", "uppercase_A", missing_path)]
    validations = [_make_validation("uppercase_A", True)]

    with pytest.raises(NormalizationError):
        normalize_glyphs(glyphs, validations, tmp_path / "out")
