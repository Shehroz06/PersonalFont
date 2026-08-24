from pathlib import Path

import cv2
import numpy as np
import pytest

from pipeline.ink_geometry import ink_pixel_count
from pipeline.segmentation.freeform import (
    FreeformExtractionConfig,
    FreeformExtractionError,
    extract_ordered_glyphs,
)


def _draw_mark(image: np.ndarray, cx: int, cy: int, size: int = 30) -> None:
    """A simple filled square 'character' mark, standard scan polarity
    (white background, black ink) — same convention real photos/scans of
    plain paper are in."""
    half = size // 2
    cv2.rectangle(image, (cx - half, cy - half), (cx + half, cy + half), (0, 0, 0), -1)


def _blank_page(size: tuple[int, int] = (400, 600)) -> np.ndarray:
    return np.full((*size, 3), 255, dtype=np.uint8)


def test_extract_ordered_glyphs_matches_row_major_reading_order(tmp_path: Path):
    image = _blank_page()
    # Row 1 (top): three marks left to right; Row 2 (bottom): two marks.
    _draw_mark(image, 100, 80)
    _draw_mark(image, 250, 80)
    _draw_mark(image, 400, 80)
    _draw_mark(image, 150, 250)
    _draw_mark(image, 350, 250)

    expected_ids = ["uppercase_A", "uppercase_B", "uppercase_C", "lowercase_d", "lowercase_e"]
    results = extract_ordered_glyphs(image, expected_ids, "job1", tmp_path, "plain.jpg")

    assert [r.character_id for r in results] == expected_ids
    assert [r.character for r in results] == ["A", "B", "C", "d", "e"]
    for r in results:
        assert Path(r.image_path).exists()
        assert r.page == 0


def test_extract_ordered_glyphs_positions_are_actually_correct(tmp_path: Path):
    # Distinguish marks by *size* so we can verify the geometry-based
    # ordering actually reflects on-page position, not just that some
    # consistent (possibly wrong) order was applied.
    image = _blank_page()
    _draw_mark(image, 100, 80, size=20)  # top-left, small
    _draw_mark(image, 400, 80, size=60)  # top-right, large
    _draw_mark(image, 250, 250, size=40)  # bottom-middle, medium

    expected_ids = ["digit_0", "digit_1", "digit_2"]  # small, large, medium in that order
    results = extract_ordered_glyphs(image, expected_ids, "job1", tmp_path, "plain.jpg")

    sizes = {r.character_id: (r.crop_box.width, r.crop_box.height) for r in results}
    assert sizes["digit_0"][0] < sizes["digit_1"][0]  # small mark matched to first expected id
    assert sizes["digit_2"][0] < sizes["digit_1"][0]  # medium mark smaller than large one


def test_extract_ordered_glyphs_raises_on_too_few_marks(tmp_path: Path):
    image = _blank_page()
    _draw_mark(image, 100, 80)
    _draw_mark(image, 250, 80)

    with pytest.raises(FreeformExtractionError):
        extract_ordered_glyphs(image, ["uppercase_A", "uppercase_B", "uppercase_C"], "job1", tmp_path, "plain.jpg")


def test_extract_ordered_glyphs_raises_on_too_many_marks(tmp_path: Path):
    image = _blank_page()
    _draw_mark(image, 100, 80)
    _draw_mark(image, 250, 80)
    _draw_mark(image, 400, 80)

    with pytest.raises(FreeformExtractionError):
        extract_ordered_glyphs(image, ["uppercase_A", "uppercase_B"], "job1", tmp_path, "plain.jpg")


def test_extract_ordered_glyphs_raises_on_blank_page(tmp_path: Path):
    image = _blank_page()

    with pytest.raises(FreeformExtractionError):
        extract_ordered_glyphs(image, ["uppercase_A"], "job1", tmp_path, "plain.jpg")


def test_extract_ordered_glyphs_raises_on_unknown_character_id(tmp_path: Path):
    image = _blank_page()
    _draw_mark(image, 100, 80)

    with pytest.raises(FreeformExtractionError):
        extract_ordered_glyphs(image, ["not_a_real_character_id"], "job1", tmp_path, "plain.jpg")


def test_extract_ordered_glyphs_ignores_tiny_noise_specks(tmp_path: Path):
    image = _blank_page()
    _draw_mark(image, 100, 80)
    _draw_mark(image, 250, 80)
    cv2.circle(image, (400, 80), 1, (0, 0, 0), -1)  # a 1-pixel speck, not a real mark

    # Should still match cleanly against 2 expected characters — the
    # speck must not be counted as a third blob.
    results = extract_ordered_glyphs(image, ["uppercase_A", "uppercase_B"], "job1", tmp_path, "plain.jpg")
    assert len(results) == 2


def test_extract_ordered_glyphs_handles_uneven_row_sizes(tmp_path: Path):
    image = _blank_page((500, 600))
    # Row 1: 4 marks; Row 2: 1 mark; Row 3: 2 marks.
    for cx in (80, 200, 320, 440):
        _draw_mark(image, cx, 60)
    _draw_mark(image, 250, 220)
    _draw_mark(image, 150, 380)
    _draw_mark(image, 350, 380)

    expected_ids = [
        "uppercase_A", "uppercase_B", "uppercase_C", "uppercase_D",
        "lowercase_e",
        "digit_0", "digit_1",
    ]
    results = extract_ordered_glyphs(image, expected_ids, "job1", tmp_path, "plain.jpg")
    assert [r.character_id for r in results] == expected_ids


def test_extract_ordered_glyphs_output_is_ink_255_convention(tmp_path: Path):
    image = _blank_page()
    _draw_mark(image, 100, 80)

    results = extract_ordered_glyphs(image, ["uppercase_A"], "job1", tmp_path, "plain.jpg")

    saved = cv2.imread(results[0].image_path, cv2.IMREAD_GRAYSCALE)
    assert set(np.unique(saved)).issubset({0, 255})
    assert ink_pixel_count(saved) > 0


def test_extract_ordered_glyphs_merges_multi_stroke_characters(tmp_path: Path):
    # Real handwriting is frequently more than one connected component per
    # character (dot+stem on "i", two dots on ":", etc — see the module
    # docstring). Simulate that here: the middle "character" is drawn as
    # two small marks a few pixels apart, standing in for a dot above a
    # stem, and must still be matched as exactly one character.
    image = _blank_page()
    _draw_mark(image, 100, 80)
    _draw_mark(image, 250, 60, size=10)  # "dot" — bottom edge at y=65
    _draw_mark(image, 250, 75, size=14)  # "stem" — top edge at y=68, 3px below the dot
    _draw_mark(image, 400, 80)

    expected_ids = ["uppercase_A", "lowercase_i", "uppercase_B"]
    results = extract_ordered_glyphs(image, expected_ids, "job1", tmp_path, "plain.jpg")

    assert [r.character_id for r in results] == expected_ids


def test_extract_ordered_glyphs_drops_border_touching_artifacts(tmp_path: Path):
    # Real phone/scanning-app photos reliably show color-fringing and
    # compression noise right at the page edge — verified on a real scan.
    # A mark touching the image border must not be counted as a character.
    image = _blank_page((400, 600))
    _draw_mark(image, 100, 80)
    _draw_mark(image, 250, 80)
    cv2.rectangle(image, (0, 0), (15, 15), (0, 0, 0), -1)  # artifact at the corner

    results = extract_ordered_glyphs(image, ["uppercase_A", "uppercase_B"], "job1", tmp_path, "plain.jpg")
    assert len(results) == 2


def test_extract_ordered_glyphs_respects_custom_config(tmp_path: Path):
    image = _blank_page()
    _draw_mark(image, 100, 80)
    cv2.circle(image, (300, 80), 5, (0, 0, 0), -1)  # a small mark, above default min-area

    # With a high min_component_area_px, the small circle should be
    # dropped as noise, leaving just 1 real mark.
    config = FreeformExtractionConfig(min_component_area_px=200)
    results = extract_ordered_glyphs(image, ["uppercase_A"], "job1", tmp_path, "plain.jpg", config=config)
    assert len(results) == 1
