import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.jobs import generate_job_id, resolve_job_paths
from app.services.pipeline_runner import PipelineError, run_pipeline
from app.services.uploads import save_local_page_file
from app.template_gen.loader import load_template_document
from pipeline.preprocessing.config import PreprocessingConfig
from tests.integration_helpers import render_clean_template_page, simulate_page_photo

TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent / "templates" / "template_v1.json"
DPI = 150.0
CHARACTERS = {"H", "I", "T", "O", "L"}


def _write_good_photo(document, page, tmp_path: Path, name: str = "page_1.jpg") -> Path:
    clean_page = render_clean_template_page(document, page, dpi=DPI, characters_to_draw=CHARACTERS)
    photo = simulate_page_photo(clean_page, canvas_size=(clean_page.shape[1] + 300, clean_page.shape[0] + 300))
    photo_path = tmp_path / name
    cv2.imwrite(str(photo_path), photo)
    return photo_path


@pytest.fixture(scope="module")
def document():
    return load_template_document(TEMPLATE_PATH)


def test_run_pipeline_raises_when_no_images_provided(tmp_path: Path, document):
    job_id = generate_job_id()
    job_paths = resolve_job_paths(tmp_path / "jobs", job_id)

    with pytest.raises(PipelineError):
        run_pipeline(job_id, [], document, job_paths)


def test_run_pipeline_raises_when_every_page_fails(tmp_path: Path, document):
    # A noisy image with no page-shaped rectangle at all -- Phase 3 page
    # detection has nothing to find.
    rng = np.random.default_rng(0)
    blank = rng.integers(0, 80, size=(400, 400, 3), dtype=np.uint8)
    bad_path = tmp_path / "unusable.jpg"
    cv2.imwrite(str(bad_path), blank)

    job_id = generate_job_id()
    job_paths = resolve_job_paths(tmp_path / "jobs", job_id)
    job_paths.ensure_dirs()
    saved = save_local_page_file(bad_path, job_paths.uploads)

    with pytest.raises(PipelineError):
        run_pipeline(job_id, [saved], document, job_paths, preprocessing_config=PreprocessingConfig(working_dpi=DPI))


def test_run_pipeline_raises_when_no_glyph_passes_validation(tmp_path: Path, document):
    page = document.pages[0]
    # A real, alignable page, but with nothing written on it.
    clean_page = render_clean_template_page(document, page, dpi=DPI, characters_to_draw=set())
    photo = simulate_page_photo(clean_page, canvas_size=(clean_page.shape[1] + 300, clean_page.shape[0] + 300))
    photo_path = tmp_path / "blank_page.jpg"
    cv2.imwrite(str(photo_path), photo)

    job_id = generate_job_id()
    job_paths = resolve_job_paths(tmp_path / "jobs", job_id)
    job_paths.ensure_dirs()
    saved = save_local_page_file(photo_path, job_paths.uploads)

    with pytest.raises(PipelineError):
        run_pipeline(job_id, [saved], document, job_paths, preprocessing_config=PreprocessingConfig(working_dpi=DPI))


def test_run_pipeline_continues_after_one_bad_page(tmp_path: Path, document):
    page = document.pages[0]
    good_path = _write_good_photo(document, page, tmp_path, "page_1.jpg")

    rng = np.random.default_rng(1)
    blank = rng.integers(0, 80, size=(400, 400, 3), dtype=np.uint8)
    bad_path = tmp_path / "page_2.jpg"
    cv2.imwrite(str(bad_path), blank)

    job_id = generate_job_id()
    job_paths = resolve_job_paths(tmp_path / "jobs", job_id)
    job_paths.ensure_dirs()
    saved_good = save_local_page_file(good_path, job_paths.uploads)
    saved_bad = save_local_page_file(bad_path, job_paths.uploads)

    result = run_pipeline(
        job_id,
        [saved_good, saved_bad],
        document,
        job_paths,
        preprocessing_config=PreprocessingConfig(working_dpi=DPI),
    )

    outcomes = {p.source_image: p for p in result.pages}
    assert outcomes[saved_good.name].succeeded is True
    assert outcomes[saved_bad.name].succeeded is False
    assert outcomes[saved_bad.name].error is not None
    assert result.font is not None  # the job still produced a font overall


def test_run_pipeline_deduplicates_the_same_page_uploaded_twice(tmp_path: Path, document):
    page = document.pages[0]
    photo_path = _write_good_photo(document, page, tmp_path, "page_1.jpg")

    job_id = generate_job_id()
    job_paths = resolve_job_paths(tmp_path / "jobs", job_id)
    job_paths.ensure_dirs()
    saved_1 = save_local_page_file(photo_path, job_paths.uploads)
    saved_2 = save_local_page_file(photo_path, job_paths.uploads)  # same source, uploaded twice

    result = run_pipeline(
        job_id,
        [saved_1, saved_2],
        document,
        job_paths,
        preprocessing_config=PreprocessingConfig(working_dpi=DPI),
    )

    character_ids = [v.character_id for v in result.validations]
    assert len(character_ids) == len(set(character_ids))  # no duplicate entries survived


def test_run_pipeline_writes_structured_log_events(tmp_path: Path, document):
    page = document.pages[0]
    photo_path = _write_good_photo(document, page, tmp_path, "page_1.jpg")

    job_id = generate_job_id()
    job_paths = resolve_job_paths(tmp_path / "jobs", job_id)
    job_paths.ensure_dirs()
    saved = save_local_page_file(photo_path, job_paths.uploads)

    result = run_pipeline(job_id, [saved], document, job_paths, preprocessing_config=PreprocessingConfig(working_dpi=DPI))

    lines = Path(result.log_path).read_text().strip().splitlines()
    events = [json.loads(line)["event"] for line in lines]

    for expected_event in (
        "JOB_CREATED",
        "PAGE_PREPROCESSED",
        "PAGE_ALIGNED",
        "GLYPHS_EXTRACTED",
        "VALIDATION_COMPLETED",
        "FONT_GENERATED",
        "JOB_COMPLETED",
    ):
        assert expected_event in events
