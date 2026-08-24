from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.jobs import generate_job_id, resolve_job_paths
from app.services.pipeline_runner import run_pipeline
from app.services.rewrite_runner import (
    RewriteError,
    characters_to_rewrite,
    read_existing_font_metadata,
    run_exclude,
    run_rewrite,
)
from app.services.uploads import save_local_page_file
from app.services.validation_store import write_validation_results
from app.template_gen.loader import load_template_document
from pipeline.font_generation.config import FontMetadata
from tests.integration_helpers import render_clean_template_page, simulate_page_photo

TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent / "templates" / "template_v1.json"
DPI = 150.0
CHARACTERS = {"H", "I", "T", "O", "L"}


@pytest.fixture(scope="module")
def document():
    return load_template_document(TEMPLATE_PATH)


def _completed_job(tmp_path: Path, document):
    """A job that's already gone through one full run_pipeline pass, with
    only CHARACTERS valid — everything else needs a rewrite."""
    page = document.pages[0]
    clean_page = render_clean_template_page(document, page, dpi=DPI, characters_to_draw=CHARACTERS)
    photo = simulate_page_photo(clean_page, canvas_size=(clean_page.shape[1] + 300, clean_page.shape[0] + 300))

    job_id = generate_job_id()
    job_paths = resolve_job_paths(tmp_path / "jobs", job_id)
    job_paths.ensure_dirs()

    photo_path = tmp_path / "page_1.jpg"
    cv2.imwrite(str(photo_path), photo)
    saved = save_local_page_file(photo_path, job_paths.uploads)

    from pipeline.preprocessing.config import PreprocessingConfig

    result = run_pipeline(job_id, [saved], document, job_paths, preprocessing_config=PreprocessingConfig(working_dpi=DPI))
    write_validation_results(job_paths, result.validations)
    return job_id, job_paths, result


def _draw_marks_grid(count: int, cols: int = 8) -> np.ndarray:
    """A blank page with ``count`` simple square marks laid out in
    row-major reading order — enough for extract_ordered_glyphs to match
    1:1 against an equally-sized expected_character_ids list."""
    rows = (count + cols - 1) // cols
    cell = 60
    image = np.full((rows * cell + cell, cols * cell + cell, 3), 255, dtype=np.uint8)
    for i in range(count):
        row, col = divmod(i, cols)
        cx = cell // 2 + cell + col * cell
        cy = cell // 2 + cell + row * cell
        half = 15
        cv2.rectangle(image, (cx - half, cy - half), (cx + half, cy + half), (0, 0, 0), -1)
    return image


def test_characters_to_rewrite_returns_only_invalid_in_canonical_order(tmp_path: Path, document):
    _, job_paths, result = _completed_job(tmp_path, document)

    to_rewrite = characters_to_rewrite(job_paths)

    rewrite_ids = {spec.character_id for spec in to_rewrite}
    valid_ids = {v.character_id for v in result.validations if v.valid}
    assert rewrite_ids.isdisjoint(valid_ids)
    assert len(to_rewrite) == len(result.validations) - len(valid_ids)

    # Canonical order == app.template_gen.character_set.get_character_set order
    from app.template_gen.character_set import get_character_set

    canonical_order = [s.character_id for s in get_character_set() if s.character_id in rewrite_ids]
    assert [s.character_id for s in to_rewrite] == canonical_order


def test_characters_to_rewrite_raises_before_job_has_ever_been_validated(tmp_path: Path):
    job_id = generate_job_id()
    job_paths = resolve_job_paths(tmp_path / "jobs", job_id)
    job_paths.ensure_dirs()

    with pytest.raises(RewriteError):
        characters_to_rewrite(job_paths)


def test_run_rewrite_merges_freeform_photo_and_increases_valid_count(tmp_path: Path, document):
    job_id, job_paths, first_result = _completed_job(tmp_path, document)
    first_valid_count = sum(1 for v in first_result.validations if v.valid)

    to_rewrite = characters_to_rewrite(job_paths)
    freeform_image = _draw_marks_grid(len(to_rewrite))

    result = run_rewrite(job_id, job_paths, freeform_image, "rewrite.jpg")

    new_valid_count = sum(1 for v in result.validations if v.valid)
    assert new_valid_count > first_valid_count

    # Every character that got a fresh mark and is a simple single-stroke
    # shape (a filled square) should now validate — spot check a few.
    valid_ids_after = {v.character_id for v in result.validations if v.valid}
    rewritten_ids = {spec.character_id for spec in to_rewrite}
    assert rewritten_ids & valid_ids_after  # at least some rewritten characters now pass


def test_run_rewrite_raises_when_nothing_left_to_rewrite(tmp_path: Path, document):
    job_id, job_paths, _ = _completed_job(tmp_path, document)
    to_rewrite = characters_to_rewrite(job_paths)

    # First rewrite clears out (most of) the invalid list.
    freeform_image = _draw_marks_grid(len(to_rewrite))
    result = run_rewrite(job_id, job_paths, freeform_image, "rewrite.jpg")
    write_validation_results(job_paths, result.validations)

    remaining = characters_to_rewrite(job_paths)
    if remaining:
        pytest.skip("Not every rewritten character validated on this run; nothing-left-to-rewrite path not reached.")

    with pytest.raises(RewriteError):
        run_rewrite(job_id, job_paths, freeform_image, "rewrite2.jpg")


def test_run_rewrite_raises_on_mismatched_mark_count(tmp_path: Path, document):
    job_id, job_paths, _ = _completed_job(tmp_path, document)
    to_rewrite = characters_to_rewrite(job_paths)

    freeform_image = _draw_marks_grid(len(to_rewrite) - 1)  # one short

    with pytest.raises(RewriteError):
        run_rewrite(job_id, job_paths, freeform_image, "rewrite.jpg")


def test_read_existing_font_metadata_recovers_family_name(tmp_path: Path, document):
    _, job_paths, _ = _completed_job(tmp_path, document)

    metadata = read_existing_font_metadata(job_paths)

    assert metadata.family_name == "PersonalFont"


def test_read_existing_font_metadata_defaults_when_job_never_packaged(tmp_path: Path):
    job_id = generate_job_id()
    job_paths = resolve_job_paths(tmp_path / "jobs", job_id)
    job_paths.ensure_dirs()

    metadata = read_existing_font_metadata(job_paths)

    assert metadata == FontMetadata()


def test_run_exclude_forces_specific_characters_invalid(tmp_path: Path, document):
    job_id, job_paths, first_result = _completed_job(tmp_path, document)
    valid_before = {v.character_id for v in first_result.validations if v.valid}
    assert valid_before, "fixture must produce at least one valid character to exclude"
    to_exclude = next(iter(valid_before))

    result = run_exclude(job_id, job_paths, [to_exclude])

    excluded_result = next(v for v in result.validations if v.character_id == to_exclude)
    assert excluded_result.valid is False
    assert excluded_result.warnings == ["Manually excluded"]

    # Nothing else's validity should have changed.
    for v in result.validations:
        if v.character_id == to_exclude:
            continue
        original = next(o for o in first_result.validations if o.character_id == v.character_id)
        assert v.valid == original.valid


def test_run_exclude_raises_on_unknown_character_id(tmp_path: Path, document):
    job_id, job_paths, _ = _completed_job(tmp_path, document)

    with pytest.raises(RewriteError):
        run_exclude(job_id, job_paths, ["not_a_real_character_id"])


def test_run_exclude_removes_excluded_glyph_from_font(tmp_path: Path, document):
    from fontTools.ttLib import TTFont

    job_id, job_paths, first_result = _completed_job(tmp_path, document)
    valid_before = {v.character_id for v in first_result.validations if v.valid}
    to_exclude = next(iter(valid_before))
    excluded_char = next(v.character for v in first_result.validations if v.character_id == to_exclude)

    result = run_exclude(job_id, job_paths, [to_exclude])

    font = TTFont(result.font.ttf_path)
    cmap = font.getBestCmap()
    assert ord(excluded_char) not in cmap
    font.close()
