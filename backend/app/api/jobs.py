"""Job lifecycle endpoints (spec §14): create a job, upload page photos,
kick off processing, and poll for results.

Processing runs via FastAPI's built-in BackgroundTasks (Starlette core —
no extra task-queue dependency, consistent with V1's "boring and
reliable" stack) rather than blocking the request for the 30-60s a full
job can take (NFR-03). Job state is persisted to disk (see
app.services.job_status) rather than kept in memory, since that's what
lets GET /status work correctly regardless of process/worker boundaries.
"""

from __future__ import annotations

import logging
from pathlib import Path

import cv2
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import get_job_paths, get_jobs_root, get_templates_root
from app.api.schemas import (
    CreateJobRequest,
    ExcludeRequest,
    ProcessJobRequest,
    RewriteCharacter,
    RewriteListResponse,
    UploadPagesResponse,
)
from app.services.freeform_job import FREEFORM_TEMPLATE_ID, run_freeform_job
from app.services.job_status import JobStatus, init_status, read_status, update_status
from app.services.jobs import JobPaths, generate_job_id, resolve_job_paths
from app.services.pipeline_runner import PipelineError, run_pipeline
from app.services.rewrite_runner import (
    RewriteError,
    characters_to_rewrite,
    read_existing_font_metadata,
    run_exclude,
    run_rewrite,
)
from app.services.uploads import UploadValidationError, save_page_bytes
from app.services.validation_store import read_validation_results, write_validation_results
from app.template_gen.loader import is_valid_template_id, load_template_document
from app.template_gen.schema import TemplateDocument
from pipeline.font_generation.config import FontMetadata
from pipeline.validation.schema import ValidationResult

router = APIRouter(prefix="/api/jobs", tags=["jobs"])
logger = logging.getLogger("personalfont.api")


def _require_status(job_paths: JobPaths) -> JobStatus:
    status = read_status(job_paths)
    if status is None:
        raise HTTPException(status_code=404, detail="Job status could not be found.")
    return status


@router.post("", response_model=JobStatus, status_code=201)
def create_job(
    request: CreateJobRequest,
    jobs_root: Path = Depends(get_jobs_root),
    templates_root: Path = Depends(get_templates_root),
) -> JobStatus:
    if not is_valid_template_id(request.template_id):
        raise HTTPException(status_code=400, detail="Invalid template id.")
    if not (templates_root / f"{request.template_id}.json").is_file():
        raise HTTPException(status_code=404, detail=f"Template {request.template_id!r} not found.")

    job_id = generate_job_id()
    job_paths = resolve_job_paths(jobs_root, job_id)
    job_paths.ensure_dirs()
    return init_status(job_paths, job_id=job_id, template_id=request.template_id)


@router.post("/{job_id}/pages", response_model=UploadPagesResponse)
async def upload_pages(
    job_id: str,
    files: list[UploadFile] = File(...),
    job_paths: JobPaths = Depends(get_job_paths),
) -> UploadPagesResponse:
    status = _require_status(job_paths)
    if status.state not in ("created", "uploading"):
        raise HTTPException(
            status_code=409, detail=f"Job {job_id!r} is already {status.state} and can't accept more pages."
        )
    if not files:
        raise HTTPException(status_code=400, detail="No files were uploaded.")

    saved = []
    try:
        for upload in files:
            content = await upload.read()
            saved.append(save_page_bytes(content, job_paths.uploads, upload.content_type))
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    pages_uploaded = len(list(job_paths.uploads.glob("page_*")))
    update_status(job_paths, state="uploading", pages_uploaded=pages_uploaded)
    return UploadPagesResponse(job_id=job_id, pages_uploaded=pages_uploaded, filenames=[p.name for p in saved])


def _run_freeform_background(
    job_id: str, job_paths: JobPaths, image_path: Path, font_metadata: FontMetadata
) -> None:
    try:
        image = cv2.imread(str(image_path))
        if image is None:
            raise PipelineError(
                f"Could not read image file: {image_path.name}. It may be corrupt or an unsupported format."
            )
        result = run_freeform_job(job_id, job_paths, image, image_path.name, font_metadata=font_metadata)
        write_validation_results(job_paths, result.validations)
        valid_count = sum(1 for v in result.validations if v.valid)
        update_status(
            job_paths,
            state="completed",
            valid_glyph_count=valid_count,
            invalid_glyph_count=len(result.validations) - valid_count,
        )
    except PipelineError as exc:
        update_status(job_paths, state="failed", error=str(exc))
    except Exception as exc:  # a job must end up "failed", never stuck at "processing" forever
        logger.exception("Unexpected error processing freeform job %s", job_id)
        update_status(job_paths, state="failed", error=f"Unexpected server error: {exc}")


@router.post("/freeform", response_model=JobStatus, status_code=202)
async def create_freeform_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    family_name: str = Form("PersonalFont"),
    creator: str = Form("PersonalFont"),
    version: str = Form("1.0"),
    description: str = Form("A personalized handwriting font generated by PersonalFont."),
    jobs_root: Path = Depends(get_jobs_root),
) -> JobStatus:
    """The no-template counterpart to POST /jobs + .../pages + .../process:
    one photo of every character in the configured set, written on plain
    paper in the fixed canonical order (spec §16's "most people won't
    reprint a template" case) — creates a job and processes it in one
    call, since there's only ever the one photo to upload."""
    job_id = generate_job_id()
    job_paths = resolve_job_paths(jobs_root, job_id)
    job_paths.ensure_dirs()
    init_status(job_paths, job_id=job_id, template_id=FREEFORM_TEMPLATE_ID)

    content = await file.read()
    try:
        saved_path = save_page_bytes(content, job_paths.uploads, file.content_type)
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    font_metadata = FontMetadata(family_name=family_name, creator=creator, version=version, description=description)
    updated = update_status(job_paths, state="processing")
    background_tasks.add_task(_run_freeform_background, job_id, job_paths, saved_path, font_metadata)
    return updated


def _run_pipeline_background(
    job_id: str,
    job_paths: JobPaths,
    document: TemplateDocument,
    font_metadata: FontMetadata,
) -> None:
    try:
        page_paths = sorted(job_paths.uploads.glob("page_*"))
        result = run_pipeline(job_id, page_paths, document, job_paths, font_metadata=font_metadata)
        write_validation_results(job_paths, result.validations)
        valid_count = sum(1 for v in result.validations if v.valid)
        update_status(
            job_paths,
            state="completed",
            valid_glyph_count=valid_count,
            invalid_glyph_count=len(result.validations) - valid_count,
        )
    except PipelineError as exc:
        update_status(job_paths, state="failed", error=str(exc))
    except Exception as exc:  # a job must end up "failed", never stuck at "processing" forever
        logger.exception("Unexpected error processing job %s", job_id)
        update_status(job_paths, state="failed", error=f"Unexpected server error: {exc}")


@router.post("/{job_id}/process", response_model=JobStatus, status_code=202)
def process_job(
    job_id: str,
    request: ProcessJobRequest,
    background_tasks: BackgroundTasks,
    job_paths: JobPaths = Depends(get_job_paths),
    templates_root: Path = Depends(get_templates_root),
) -> JobStatus:
    status = _require_status(job_paths)
    if status.pages_uploaded < 1:
        raise HTTPException(status_code=409, detail="No pages have been uploaded for this job yet.")
    if status.state in ("processing", "completed"):
        raise HTTPException(status_code=409, detail=f"Job {job_id!r} is already {status.state}.")

    document = load_template_document(templates_root / f"{status.template_id}.json")
    font_metadata = FontMetadata(
        family_name=request.family_name,
        creator=request.creator,
        version=request.version,
        description=request.description,
    )

    updated = update_status(job_paths, state="processing", error=None)
    background_tasks.add_task(_run_pipeline_background, job_id, job_paths, document, font_metadata)
    return updated


@router.get("/{job_id}/status", response_model=JobStatus)
def get_status(job_paths: JobPaths = Depends(get_job_paths)) -> JobStatus:
    return _require_status(job_paths)


@router.get("/{job_id}/validation", response_model=list[ValidationResult])
def get_validation(job_paths: JobPaths = Depends(get_job_paths)) -> list[ValidationResult]:
    status = _require_status(job_paths)
    if status.state != "completed":
        raise HTTPException(status_code=409, detail=f"Job is {status.state}; validation results aren't available yet.")
    return read_validation_results(job_paths)


@router.get("/{job_id}/rewrite-list", response_model=RewriteListResponse)
def get_rewrite_list(job_id: str, job_paths: JobPaths = Depends(get_job_paths)) -> RewriteListResponse:
    """The characters this job still needs, in the exact order they must
    be written in on a blank sheet (see app.services.rewrite_runner) — the
    frontend shows this list to the user before they photograph a rewrite."""
    status = _require_status(job_paths)
    if status.state != "completed":
        raise HTTPException(status_code=409, detail=f"Job is {status.state}; nothing to rewrite yet.")

    try:
        specs = characters_to_rewrite(job_paths)
    except RewriteError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return RewriteListResponse(
        job_id=job_id,
        characters=[RewriteCharacter(character_id=s.character_id, character=s.character) for s in specs],
    )


def _run_rewrite_background(job_id: str, job_paths: JobPaths, image_path: Path, font_metadata: FontMetadata) -> None:
    try:
        image = cv2.imread(str(image_path))
        if image is None:
            raise RewriteError(f"Could not read image file: {image_path.name}. It may be corrupt or an unsupported format.")

        result = run_rewrite(job_id, job_paths, image, image_path.name, font_metadata=font_metadata)
        write_validation_results(job_paths, result.validations)
        valid_count = sum(1 for v in result.validations if v.valid)
        update_status(
            job_paths,
            state="completed",
            valid_glyph_count=valid_count,
            invalid_glyph_count=len(result.validations) - valid_count,
        )
    except RewriteError as exc:
        update_status(job_paths, state="failed", error=str(exc))
    except Exception as exc:  # a job must end up "failed", never stuck at "processing" forever
        logger.exception("Unexpected error rewriting job %s", job_id)
        update_status(job_paths, state="failed", error=f"Unexpected server error: {exc}")


@router.post("/{job_id}/rewrite", response_model=JobStatus, status_code=202)
async def rewrite_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    job_paths: JobPaths = Depends(get_job_paths),
) -> JobStatus:
    """Accepts one plain-paper photo of the job's still-needed characters
    (see GET .../rewrite-list for what/order), merges them into the job,
    and regenerates its font — without requiring the template to be
    reprinted. Only valid once a job has completed at least one full run,
    since a rewrite patches an existing job rather than creating one."""
    status = _require_status(job_paths)
    if status.state != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Job is {status.state}; it must finish processing before you can rewrite characters.",
        )

    content = await file.read()
    try:
        saved_path = save_page_bytes(content, job_paths.uploads, file.content_type)
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    font_metadata = read_existing_font_metadata(job_paths)
    updated = update_status(job_paths, state="processing", error=None)
    background_tasks.add_task(_run_rewrite_background, job_id, job_paths, saved_path, font_metadata)
    return updated


def _run_exclude_background(
    job_id: str, job_paths: JobPaths, character_ids: list[str], font_metadata: FontMetadata
) -> None:
    try:
        result = run_exclude(job_id, job_paths, character_ids, font_metadata=font_metadata)
        write_validation_results(job_paths, result.validations)
        valid_count = sum(1 for v in result.validations if v.valid)
        update_status(
            job_paths,
            state="completed",
            valid_glyph_count=valid_count,
            invalid_glyph_count=len(result.validations) - valid_count,
        )
    except RewriteError as exc:
        update_status(job_paths, state="failed", error=str(exc))
    except Exception as exc:  # a job must end up "failed", never stuck at "processing" forever
        logger.exception("Unexpected error excluding characters for job %s", job_id)
        update_status(job_paths, state="failed", error=f"Unexpected server error: {exc}")


@router.post("/{job_id}/exclude", response_model=JobStatus, status_code=202)
def exclude_characters(
    job_id: str,
    request: ExcludeRequest,
    background_tasks: BackgroundTasks,
    job_paths: JobPaths = Depends(get_job_paths),
) -> JobStatus:
    """Rebuilds the font leaving out specific characters the user chose
    to drop on purpose (not a validation failure — e.g. odd stroke
    layering they just don't want in the font). No photo involved, just
    a list of character_ids to force out of this run."""
    status = _require_status(job_paths)
    if status.state != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Job is {status.state}; it must finish processing before you can exclude characters.",
        )
    if not request.character_ids:
        raise HTTPException(status_code=400, detail="No character ids were provided.")

    font_metadata = read_existing_font_metadata(job_paths)
    updated = update_status(job_paths, state="processing", error=None)
    background_tasks.add_task(_run_exclude_background, job_id, job_paths, request.character_ids, font_metadata)
    return updated


_DOWNLOAD_MEDIA_TYPES = {"ttf": "font/ttf", "otf": "font/otf", "zip": "application/zip"}


@router.get("/{job_id}/download")
def download_font(format: str = "zip", job_paths: JobPaths = Depends(get_job_paths)) -> FileResponse:
    """Defaults to the full package (spec §13: MyFont.zip). ``format=ttf``
    / ``format=otf`` remain available for fetching the raw font directly
    (e.g. the frontend's in-browser FontFace preview)."""
    status = _require_status(job_paths)
    if status.state != "completed":
        raise HTTPException(status_code=409, detail=f"Job is {status.state}; no font is available yet.")
    if format not in _DOWNLOAD_MEDIA_TYPES:
        raise HTTPException(status_code=400, detail="format must be 'zip', 'ttf', or 'otf'.")

    matches = list(job_paths.font.glob(f"*.{format}"))
    if not matches:
        raise HTTPException(status_code=404, detail=f"No .{format} file was found for this job.")

    return FileResponse(matches[0], filename=matches[0].name, media_type=_DOWNLOAD_MEDIA_TYPES[format])


_PREVIEW_MEDIA_TYPES = {"png": "image/png", "pdf": "application/pdf"}


@router.get("/{job_id}/preview")
def get_preview(format: str = "png", job_paths: JobPaths = Depends(get_job_paths)) -> FileResponse:
    status = _require_status(job_paths)
    if status.state != "completed":
        raise HTTPException(status_code=409, detail=f"Job is {status.state}; no preview is available yet.")
    if format not in _PREVIEW_MEDIA_TYPES:
        raise HTTPException(status_code=400, detail="format must be 'png' or 'pdf'.")

    preview_path = job_paths.preview / f"preview.{format}"
    if not preview_path.is_file():
        raise HTTPException(status_code=404, detail=f"No preview.{format} was found for this job.")

    return FileResponse(preview_path, filename=preview_path.name, media_type=_PREVIEW_MEDIA_TYPES[format])
