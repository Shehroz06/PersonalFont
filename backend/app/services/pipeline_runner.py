"""Phase 10: the end-to-end V1 pipeline (spec FR-13) — chains every stage
built in Phases 3-9 for one job:

    upload -> preprocess -> align -> extract -> validate -> normalize
    -> vectorize -> generate font

Preview and packaging (spec §12-13) are Phase 13's concern; this stops at
a saved TTF/OTF pair.

Resilience follows the same "one bad unit doesn't sink the batch"
principle used throughout the pipeline (spec §16/NFR-06), just applied
one level up: a page that fails to preprocess/align/extract is recorded
as a failed PageOutcome and skipped, not raised — the job only fails
outright (PipelineError) if *no* page produced any glyphs, or *no* glyph
passed validation, since neither case can produce a font at all.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import cv2

from app.services.job_logging import get_job_logger, log_event
from app.services.jobs import JobPaths
from app.template_gen.schema import TemplateDocument
from pipeline.alignment.align import align_page_to_template
from pipeline.alignment.errors import AlignmentError
from pipeline.font_generation.build import generate_fonts
from pipeline.font_generation.config import FontGenerationConfig, FontMetadata
from pipeline.font_generation.schema import GeneratedFont
from pipeline.normalization.normalize import normalize_glyphs
from pipeline.preprocessing.config import PreprocessingConfig
from pipeline.preprocessing.errors import PreprocessingError
from pipeline.preprocessing.pipeline import preprocess_page
from pipeline.segmentation.errors import SegmentationError
from pipeline.segmentation.extract import extract_glyphs
from pipeline.segmentation.schema import ExtractedGlyph
from pipeline.validation.schema import ValidationResult
from pipeline.validation.validate import validate_glyphs
from pipeline.vectorization.trace import vectorize_glyphs


class PipelineError(Exception):
    """Raised when the job cannot produce a font at all — distinct from a
    single page or glyph failing, both of which the pipeline tolerates
    and reports in the result instead of raising."""


@dataclass(frozen=True)
class PageOutcome:
    source_image: str
    succeeded: bool
    template_page: int | None = None
    alignment_confidence: float | None = None
    glyphs_extracted: int = 0
    error: str | None = None


@dataclass(frozen=True)
class PipelineResult:
    job_id: str
    pages: list[PageOutcome]
    validations: list[ValidationResult]
    font: GeneratedFont
    log_path: str


def _save_uploads(image_paths: list[Path], uploads_dir: Path) -> list[Path]:
    """Copy each uploaded image into the job's own uploads/ directory
    under a generated filename — never trust or reuse a caller-supplied
    path/filename beyond this point (spec §18)."""
    uploads_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    for index, source in enumerate(image_paths, start=1):
        suffix = source.suffix.lower() if source.suffix.lower() in (".jpg", ".jpeg", ".png") else ".jpg"
        destination = uploads_dir / f"page_{index}{suffix}"
        shutil.copyfile(source, destination)
        saved.append(destination)
    return saved


def _process_page(
    image_path: Path,
    template_document: TemplateDocument,
    job_id: str,
    job_paths: JobPaths,
    preprocessing_config: PreprocessingConfig,
    logger,
) -> tuple[PageOutcome, list[ExtractedGlyph]]:
    image = cv2.imread(str(image_path))
    if image is None:
        error = f"Could not read image file: {image_path.name}. It may be corrupt or an unsupported format."
        log_event(logger, "PAGE_FAILED", source_image=image_path.name, error=error)
        return PageOutcome(source_image=image_path.name, succeeded=False, error=error), []

    try:
        preprocessed = preprocess_page(image, preprocessing_config)
        log_event(logger, "PAGE_PREPROCESSED", source_image=image_path.name)

        alignment = align_page_to_template(
            preprocessed.deskewed, template_document, dpi=preprocessing_config.working_dpi
        )
        log_event(
            logger,
            "PAGE_ALIGNED",
            source_image=image_path.name,
            template_page=alignment.page.page,
            confidence=alignment.confidence,
        )

        glyphs = extract_glyphs(
            image=alignment.aligned_image,
            page=alignment.page,
            page_height_pt=template_document.page_size.height,
            dpi=preprocessing_config.working_dpi,
            job_id=job_id,
            output_dir=job_paths.glyphs,
            source_image=image_path.name,
            extraction_confidence=alignment.confidence,
        )
        log_event(logger, "GLYPHS_EXTRACTED", source_image=image_path.name, count=len(glyphs))

        outcome = PageOutcome(
            source_image=image_path.name,
            succeeded=True,
            template_page=alignment.page.page,
            alignment_confidence=alignment.confidence,
            glyphs_extracted=len(glyphs),
        )
        return outcome, glyphs

    except (PreprocessingError, AlignmentError, SegmentationError) as exc:
        log_event(logger, "PAGE_FAILED", source_image=image_path.name, error=str(exc))
        return PageOutcome(source_image=image_path.name, succeeded=False, error=str(exc)), []


def _deduplicate_glyphs(glyphs: list[ExtractedGlyph], logger) -> list[ExtractedGlyph]:
    """If the same character was extracted more than once (e.g. the same
    physical page uploaded twice), keep only the highest-confidence copy
    rather than passing an ambiguous duplicate character_id into font
    generation."""
    best_by_id: dict[str, ExtractedGlyph] = {}
    for glyph in glyphs:
        existing = best_by_id.get(glyph.character_id)
        if existing is None:
            best_by_id[glyph.character_id] = glyph
        elif glyph.extraction_confidence > existing.extraction_confidence:
            log_event(
                logger,
                "DUPLICATE_GLYPH_DISCARDED",
                character_id=glyph.character_id,
                discarded_source=existing.source_image,
                kept_source=glyph.source_image,
            )
            best_by_id[glyph.character_id] = glyph
        else:
            log_event(
                logger,
                "DUPLICATE_GLYPH_DISCARDED",
                character_id=glyph.character_id,
                discarded_source=glyph.source_image,
                kept_source=existing.source_image,
            )
    return list(best_by_id.values())


def run_pipeline(
    job_id: str,
    image_paths: list[Path],
    template_document: TemplateDocument,
    job_paths: JobPaths,
    font_metadata: FontMetadata | None = None,
    preprocessing_config: PreprocessingConfig | None = None,
    font_config: FontGenerationConfig | None = None,
) -> PipelineResult:
    if not image_paths:
        raise PipelineError("No page images were provided.")

    preprocessing_config = preprocessing_config or PreprocessingConfig()
    font_metadata = font_metadata or FontMetadata()

    job_paths.ensure_dirs()
    logger = get_job_logger(job_id, job_paths.logs)
    log_event(logger, "JOB_CREATED", job_id=job_id, page_count=len(image_paths))

    saved_images = _save_uploads(image_paths, job_paths.uploads)

    pages: list[PageOutcome] = []
    all_glyphs: list[ExtractedGlyph] = []
    for image_path in saved_images:
        outcome, glyphs = _process_page(image_path, template_document, job_id, job_paths, preprocessing_config, logger)
        pages.append(outcome)
        all_glyphs.extend(glyphs)

    if not all_glyphs:
        log_event(logger, "JOB_FAILED", reason="no_pages_processed")
        raise PipelineError(
            "None of the uploaded pages could be processed. Please check each page's error "
            "below and re-upload clearer photographs."
        )

    all_glyphs = _deduplicate_glyphs(all_glyphs, logger)

    validations = validate_glyphs(all_glyphs)
    valid_count = sum(1 for v in validations if v.valid)
    log_event(
        logger,
        "VALIDATION_COMPLETED",
        total=len(validations),
        valid=valid_count,
        invalid=len(validations) - valid_count,
    )

    normalized = normalize_glyphs(all_glyphs, validations, job_paths.processed)
    if not normalized:
        log_event(logger, "JOB_FAILED", reason="no_valid_glyphs")
        raise PipelineError(
            "No characters passed validation, so no font can be generated. Please review the "
            "validation warnings and re-upload clearer photographs of the affected pages."
        )

    vectorized = vectorize_glyphs(normalized, job_paths.svg)
    font = generate_fonts(vectorized, job_paths.font, metadata=font_metadata, config=font_config)
    log_event(logger, "FONT_GENERATED", family_name=font.family_name, glyph_count=font.glyph_count)

    log_event(logger, "JOB_COMPLETED", job_id=job_id)

    return PipelineResult(
        job_id=job_id,
        pages=pages,
        validations=validations,
        font=font,
        log_path=str(job_paths.logs / "pipeline.log"),
    )
