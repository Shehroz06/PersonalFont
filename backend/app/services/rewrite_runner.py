"""Lets a user fix specific flagged characters on an already-completed job
by writing them on a blank sheet of paper — no template reprint, no ArUco
markers required — instead of resubmitting the whole job.

Builds on pipeline.segmentation.freeform (plain-paper extraction, matched
in row-major order against a caller-supplied character list) and reuses
pipeline_runner.finalize_job for the validate -> ... -> package tail, so a
rewrite goes through exactly the same checks a fresh job does.

The character list a user must write, and the order to write them in, is
never accepted from the caller — it's always recomputed here from the
job's own validation.json (characters_to_rewrite), in the character set's
fixed canonical order. Accepting caller-supplied ids would let a client
request mismatched ordering that silently mislabels glyphs; recomputing
it here is also what lets GET /rewrite-list and the POST that consumes
the resulting photo agree on the list without the client ever having to
round-trip it itself.
"""

from __future__ import annotations

import json

import numpy as np

from app.services.job_logging import get_job_logger, log_event
from app.services.jobs import JobPaths
from app.services.pipeline_runner import PageOutcome, PipelineResult, finalize_job
from app.services.validation_store import read_validation_results
from app.template_gen.character_set import CharacterSpec, character_set_by_id, get_character_set
from pipeline.font_generation.config import FontGenerationConfig, FontMetadata
from pipeline.segmentation.freeform import FREEFORM_PAGE_SENTINEL, FreeformExtractionError, extract_ordered_glyphs
from pipeline.segmentation.schema import ExtractedGlyph, GlyphCropBox


class RewriteError(Exception):
    """Raised when a rewrite can't be applied — always with a message
    safe to show the end user directly (spec §17), same convention as
    PipelineError and FreeformExtractionError."""


def characters_to_rewrite(job_paths: JobPaths) -> list[CharacterSpec]:
    """The characters this job still needs, in the fixed order the user
    must write them in (canonical character-set order, not the order
    validation happened to run in — extract_ordered_glyphs matches purely
    by position, so both GET /rewrite-list and the extraction that later
    consumes the photo must agree on one stable order).

    Raises RewriteError if the job has no validation results yet (it
    hasn't completed a first run) — there's nothing to rewrite before
    that.
    """
    validations = read_validation_results(job_paths)
    if not validations:
        raise RewriteError("This job has no validation results yet. Process it before rewriting characters.")

    invalid_ids = {v.character_id for v in validations if not v.valid}
    return [spec for spec in get_character_set() if spec.character_id in invalid_ids]


def _all_glyphs_from_disk(
    job_id: str, job_paths: JobPaths, source_overrides: dict[str, str] | None = None
) -> list[ExtractedGlyph]:
    """Rebuilds the job's full ExtractedGlyph list from whatever PNGs
    currently sit in job_paths.glyphs — the source of truth for "what
    characters does this job have" once a job is already past its first
    run, since nothing else persists the original per-glyph metadata.
    ``source_overrides`` lets a caller record which character_ids came
    from a just-processed photo rather than an earlier run, purely for
    logging/traceability; it has no effect on validation or the font."""
    source_overrides = source_overrides or {}
    spec_by_id = character_set_by_id()
    glyphs: list[ExtractedGlyph] = []
    for png in sorted(job_paths.glyphs.glob("*.png")):
        spec = spec_by_id.get(png.stem)
        if spec is None:
            continue
        glyphs.append(
            ExtractedGlyph(
                job_id=job_id,
                page=FREEFORM_PAGE_SENTINEL,
                character=spec.character,
                character_id=png.stem,
                source_image=source_overrides.get(png.stem, "existing"),
                crop_box=GlyphCropBox(x=0, y=0, width=1, height=1),
                extraction_confidence=1.0,
                image_path=str(png),
            )
        )
    return glyphs


def run_rewrite(
    job_id: str,
    job_paths: JobPaths,
    freeform_image: np.ndarray,
    source_image: str,
    font_metadata: FontMetadata | None = None,
    font_config: FontGenerationConfig | None = None,
) -> PipelineResult:
    """Extract the job's still-needed characters from ``freeform_image``
    (a plain-paper photo), merge them into the job's existing glyph crops
    (overwriting only the ones just rewritten), and rebuild the font from
    the full, updated set.

    Raises RewriteError if there's nothing left to rewrite, or if the
    photo's detected marks don't match the expected characters 1:1 (see
    pipeline.segmentation.freeform's module docstring for why that's a
    hard failure rather than a best-effort guess).
    """
    font_metadata = font_metadata or FontMetadata()
    job_paths.ensure_dirs()
    logger = get_job_logger(job_id, job_paths.logs)

    to_rewrite = characters_to_rewrite(job_paths)
    if not to_rewrite:
        raise RewriteError("Every character in this job already passed validation. There's nothing to rewrite.")

    expected_ids = [spec.character_id for spec in to_rewrite]
    log_event(logger, "REWRITE_STARTED", source_image=source_image, expected_count=len(expected_ids))

    try:
        extract_ordered_glyphs(
            image=freeform_image,
            expected_character_ids=expected_ids,
            job_id=job_id,
            output_dir=job_paths.glyphs,
            source_image=source_image,
        )
    except FreeformExtractionError as exc:
        log_event(logger, "REWRITE_FAILED", error=str(exc))
        raise RewriteError(str(exc)) from exc

    log_event(logger, "REWRITE_EXTRACTED", count=len(expected_ids))

    source_overrides = {cid: source_image for cid in expected_ids}
    all_glyphs = _all_glyphs_from_disk(job_id, job_paths, source_overrides)

    pages = [PageOutcome(source_image=source_image, succeeded=True, glyphs_extracted=len(expected_ids))]
    return finalize_job(job_id, job_paths, pages, all_glyphs, "freeform_rewrite", font_metadata, font_config, logger)


def run_exclude(
    job_id: str,
    job_paths: JobPaths,
    excluded_character_ids: list[str],
    font_metadata: FontMetadata | None = None,
    font_config: FontGenerationConfig | None = None,
) -> PipelineResult:
    """Rebuilds the font leaving out ``excluded_character_ids`` — for a
    character that's technically valid but the user doesn't want in the
    font anyway (odd stroke layering, a shape they just don't like), not
    a validation failure. No new photo is involved: this just re-runs
    normalize -> vectorize -> generate -> preview -> package against the
    job's existing glyphs, forcing the excluded ids to read as invalid
    (with a distinct "manually excluded" reason) regardless of what
    Phase 6 validation originally said about them.

    Raises RewriteError for an unknown character_id, so a stale or
    tampered request can't silently no-op.
    """
    font_metadata = font_metadata or FontMetadata()
    job_paths.ensure_dirs()
    logger = get_job_logger(job_id, job_paths.logs)

    spec_by_id = character_set_by_id()
    unknown = [cid for cid in excluded_character_ids if cid not in spec_by_id]
    if unknown:
        raise RewriteError(f"Unknown character id(s): {', '.join(unknown)}.")

    log_event(logger, "EXCLUDE_STARTED", excluded_count=len(excluded_character_ids))

    all_glyphs = _all_glyphs_from_disk(job_id, job_paths)
    pages: list[PageOutcome] = []
    return finalize_job(
        job_id,
        job_paths,
        pages,
        all_glyphs,
        "exclude",
        font_metadata,
        font_config,
        logger,
        force_invalid_ids=frozenset(excluded_character_ids),
    )


def read_existing_font_metadata(job_paths: JobPaths) -> FontMetadata:
    """Best-effort recovery of the font metadata a job was originally
    generated with, so a rewrite regenerates the *same* font rather than
    silently resetting its name/creator/version back to defaults. Falls
    back to defaults if the job has no packaged metadata.json yet (e.g.
    its first run failed before packaging)."""
    metadata_path = job_paths.font / "metadata.json"
    if not metadata_path.is_file():
        return FontMetadata()

    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    return FontMetadata(
        family_name=data.get("family_name", FontMetadata.family_name),
        style_name=data.get("style_name", FontMetadata.style_name),
        version=data.get("version", FontMetadata.version),
        creator=data.get("creator", FontMetadata.creator),
        description=data.get("description", FontMetadata.description),
    )
