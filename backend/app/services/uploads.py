"""Validates and safely saves uploaded page images into a job's uploads/
directory (spec §18: upload size limits, MIME/type validation, safe
filenames — never trust a caller-supplied filename or path).

Kept separate from pipeline_runner.run_pipeline so uploads can be
validated and saved as their own step, independent of when processing
actually starts — the API needs pages uploaded via one request
(POST /jobs/{id}/pages) well before processing is triggered by another
(POST /jobs/{id}/process), while the CLI does both back-to-back from
local files.
"""

from __future__ import annotations

import shutil
from pathlib import Path

MAX_UPLOAD_BYTES = 15 * 1024 * 1024  # 15 MB per page image

# Only raster formats our preprocessing pipeline (OpenCV-based) can read
# directly. PDF is explicitly "optional" per FR-02 and not implemented in
# V1.
ALLOWED_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
}


class UploadValidationError(Exception):
    """Raised for an invalid upload — always with a message safe to show
    the end user directly (spec §17)."""


def validate_upload_size(size_bytes: int, max_bytes: int = MAX_UPLOAD_BYTES) -> None:
    if size_bytes > max_bytes:
        raise UploadValidationError(
            f"File is too large ({size_bytes / (1024 * 1024):.1f} MB). "
            f"The limit is {max_bytes / (1024 * 1024):.0f} MB per page."
        )
    if size_bytes == 0:
        raise UploadValidationError("Uploaded file is empty.")


def _extension_for_content_type(content_type: str | None) -> str:
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise UploadValidationError(
            f"Unsupported file type {content_type!r}. Only JPEG and PNG images are accepted."
        )
    return ALLOWED_CONTENT_TYPES[content_type]


def _next_page_path(uploads_dir: Path, extension: str) -> Path:
    existing = list(uploads_dir.glob("page_*"))
    return uploads_dir / f"page_{len(existing) + 1}{extension}"


def save_page_bytes(
    content: bytes,
    uploads_dir: Path,
    content_type: str | None,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> Path:
    """Validate and save one uploaded page's raw bytes (API upload path).
    Returns the path it was saved to, under a generated safe filename —
    the original filename is never used."""
    validate_upload_size(len(content), max_bytes)
    extension = _extension_for_content_type(content_type)

    uploads_dir.mkdir(parents=True, exist_ok=True)
    destination = _next_page_path(uploads_dir, extension)
    destination.write_bytes(content)
    return destination


def save_local_page_file(source: Path, uploads_dir: Path, max_bytes: int = MAX_UPLOAD_BYTES) -> Path:
    """Validate and save a page image already sitting on local disk (CLI
    path) — same size limit and safe-filename generation as the API
    upload path, minus content-type sniffing (the CLI trusts the local
    file's own extension instead of an HTTP header)."""
    if not source.is_file():
        raise UploadValidationError(f"File not found: {source}")

    validate_upload_size(source.stat().st_size, max_bytes)

    suffix = source.suffix.lower()
    extension = suffix if suffix in (".jpg", ".jpeg", ".png") else ".jpg"

    uploads_dir.mkdir(parents=True, exist_ok=True)
    destination = _next_page_path(uploads_dir, extension)
    shutil.copyfile(source, destination)
    return destination
