"""Creates a font entirely from a plain-paper photo — the writer fills in
every character of the character set (in the fixed canonical order from
app.template_gen.character_set.get_character_set) on a blank sheet, no
printed template or ArUco markers involved at all.

This is the from-scratch counterpart to app.services.rewrite_runner: a
rewrite patches specific characters into a job that already exists,
while this creates one from nothing. Both sit on the same primitive —
pipeline.segmentation.freeform.extract_ordered_glyphs matching detected
ink blobs against a caller-supplied ordered character list — and both
finish through pipeline_runner.finalize_job's validate -> ... -> package
tail, since a font is always built from a job's full glyph set together.
"""

from __future__ import annotations

import numpy as np

from app.services.job_logging import get_job_logger, log_event
from app.services.jobs import JobPaths
from app.services.pipeline_runner import PageOutcome, PipelineError, PipelineResult, finalize_job
from app.template_gen.character_set import get_character_set
from pipeline.font_generation.config import FontGenerationConfig, FontMetadata
from pipeline.segmentation.freeform import FreeformExtractionError, extract_ordered_glyphs
from pipeline.segmentation.schema import ExtractedGlyph

FREEFORM_TEMPLATE_ID = "freeform"


def run_freeform_job(
    job_id: str,
    job_paths: JobPaths,
    image: np.ndarray,
    source_image: str,
    font_metadata: FontMetadata | None = None,
    font_config: FontGenerationConfig | None = None,
) -> PipelineResult:
    """Extract every character in the configured set from ``image`` (one
    plain-paper photo, characters written in get_character_set() order)
    and build a font from it.

    Raises PipelineError if the photo's detected marks don't match the
    full character set 1:1 — see pipeline.segmentation.freeform's module
    docstring for why that's a hard failure rather than a best-effort
    guess.
    """
    font_metadata = font_metadata or FontMetadata()
    job_paths.ensure_dirs()
    logger = get_job_logger(job_id, job_paths.logs)

    expected_ids = [spec.character_id for spec in get_character_set()]
    log_event(logger, "FREEFORM_JOB_STARTED", source_image=source_image, expected_count=len(expected_ids))

    try:
        glyphs: list[ExtractedGlyph] = extract_ordered_glyphs(
            image=image,
            expected_character_ids=expected_ids,
            job_id=job_id,
            output_dir=job_paths.glyphs,
            source_image=source_image,
        )
    except FreeformExtractionError as exc:
        log_event(logger, "JOB_FAILED", reason="freeform_extraction_failed", error=str(exc))
        raise PipelineError(str(exc)) from exc

    log_event(logger, "GLYPHS_EXTRACTED", source_image=source_image, count=len(glyphs))

    pages = [PageOutcome(source_image=source_image, succeeded=True, glyphs_extracted=len(glyphs))]
    return finalize_job(job_id, job_paths, pages, glyphs, FREEFORM_TEMPLATE_ID, font_metadata, font_config, logger)
