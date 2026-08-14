from pathlib import Path

import cv2

from pipeline.segmentation.schema import ExtractedGlyph, GlyphCropBox
from pipeline.validation.config import ValidationConfig
from pipeline.validation.rules import (
    check_component_count,
    check_foreground_ratio,
    check_glyph_size,
    check_touches_boundary,
    expected_component_range,
)
from pipeline.validation.validate import validate_glyph, validate_glyphs
from tests.validation_helpers import (
    blank_crop,
    boundary_touching_crop,
    clean_letter_crop,
    noisy_crop,
    sparse_dot_crop,
    two_dot_crop,
)

CONFIG = ValidationConfig()


# --- individual rules ------------------------------------------------------


def test_expected_component_range_default_is_single_stroke():
    assert expected_component_range("A") == (1, 1)


def test_expected_component_range_allows_two_for_colon_and_i_j():
    assert expected_component_range(":")[1] >= 2
    assert expected_component_range("i")[1] >= 2
    assert expected_component_range("j")[1] >= 2


def test_check_component_count_accepts_two_dots_for_colon():
    score, warning = check_component_count(two_dot_crop(), ":")

    assert score == 1.0
    assert warning is None


def test_check_component_count_flags_two_components_for_single_stroke_char():
    score, warning = check_component_count(two_dot_crop(), "A")

    assert score < 1.0
    assert warning == "Unexpected number of disconnected strokes"


def test_check_foreground_ratio_flags_sparse_ink():
    score, warning = check_foreground_ratio(sparse_dot_crop(), CONFIG)

    assert score < CONFIG.warning_score_threshold
    assert warning == "Insufficient foreground pixels"


def test_check_foreground_ratio_flags_excessive_noise():
    score, warning = check_foreground_ratio(noisy_crop(), CONFIG)

    assert score < CONFIG.warning_score_threshold
    assert warning == "Excessive noise"


def test_check_foreground_ratio_accepts_clean_letter():
    score, warning = check_foreground_ratio(clean_letter_crop(), CONFIG)

    assert score == 1.0
    assert warning is None


def test_check_glyph_size_flags_tiny_glyph():
    score, warning = check_glyph_size(sparse_dot_crop(), CONFIG)

    assert score < 1.0
    assert warning == "Glyph is extremely small"


def test_check_touches_boundary_flags_touching_glyph():
    score, warning = check_touches_boundary(boundary_touching_crop(), CONFIG)

    assert score == CONFIG.boundary_touch_score
    assert warning is not None


def test_check_touches_boundary_accepts_centered_glyph():
    score, warning = check_touches_boundary(clean_letter_crop(), CONFIG)

    assert score == 1.0
    assert warning is None


# --- validate_glyph (single image) -----------------------------------------


def test_validate_glyph_clean_letter_is_valid_with_no_warnings():
    result = validate_glyph(clean_letter_crop(), "L", "uppercase_L")

    assert result.valid is True
    assert result.warnings == []
    assert result.confidence > 0.9


def test_validate_glyph_blank_is_invalid_and_empty():
    result = validate_glyph(blank_crop(), "A", "uppercase_A")

    assert result.valid is False
    assert result.confidence == 0.0
    assert "Empty glyph" in result.warnings[0]


def test_validate_glyph_sparse_dot_is_invalid():
    result = validate_glyph(sparse_dot_crop(), "A", "uppercase_A")

    assert result.valid is False
    assert "Insufficient foreground pixels" in result.warnings


def test_validate_glyph_noisy_is_invalid():
    result = validate_glyph(noisy_crop(), "A", "uppercase_A")

    assert result.valid is False
    assert "Excessive noise" in result.warnings


def test_validate_glyph_boundary_touch_lowers_confidence_but_not_to_zero():
    result = validate_glyph(boundary_touching_crop(), "A", "uppercase_A")

    assert result.valid is False
    assert 0.0 < result.confidence < 1.0
    assert any("boundary" in w for w in result.warnings)


def test_validate_glyph_matches_spec_response_shape():
    result = validate_glyph(clean_letter_crop(), "A", "uppercase_A")
    payload = result.model_dump()

    assert set(payload.keys()) >= {"character", "valid", "confidence", "warnings"}
    assert isinstance(payload["warnings"], list)


# --- validate_glyphs (batch) ------------------------------------------------


def _make_glyph(image_path: Path, character: str, character_id: str) -> ExtractedGlyph:
    return ExtractedGlyph(
        job_id="testjob",
        page=1,
        character=character,
        character_id=character_id,
        source_image="page_1.png",
        crop_box=GlyphCropBox(x=0, y=0, width=60, height=60),
        extraction_confidence=1.0,
        image_path=str(image_path),
    )


def test_validate_glyphs_handles_a_mix_of_good_and_bad(tmp_path: Path):
    good_path = tmp_path / "uppercase_L.png"
    bad_path = tmp_path / "uppercase_A.png"
    cv2.imwrite(str(good_path), clean_letter_crop())
    cv2.imwrite(str(bad_path), blank_crop())

    glyphs = [_make_glyph(good_path, "L", "uppercase_L"), _make_glyph(bad_path, "A", "uppercase_A")]
    results = validate_glyphs(glyphs)

    assert len(results) == 2
    assert results[0].valid is True
    assert results[1].valid is False


def test_validate_glyphs_does_not_raise_when_one_image_is_unreadable(tmp_path: Path):
    good_path = tmp_path / "uppercase_L.png"
    missing_path = tmp_path / "does_not_exist.png"
    cv2.imwrite(str(good_path), clean_letter_crop())

    glyphs = [_make_glyph(good_path, "L", "uppercase_L"), _make_glyph(missing_path, "A", "uppercase_A")]

    results = validate_glyphs(glyphs)  # must not raise

    assert len(results) == 2
    assert results[0].valid is True
    assert results[1].valid is False
    assert results[1].warnings
