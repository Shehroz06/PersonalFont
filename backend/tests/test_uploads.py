from pathlib import Path

import numpy as np
import pytest

from app.services.uploads import (
    MAX_UPLOAD_BYTES,
    UploadValidationError,
    save_local_page_file,
    save_page_bytes,
    validate_upload_size,
)


def _fake_jpeg_bytes(size: int = 1024) -> bytes:
    return np.random.default_rng(0).integers(0, 255, size=size, dtype=np.uint8).tobytes()


def test_validate_upload_size_accepts_normal_file():
    validate_upload_size(1024)  # must not raise


def test_validate_upload_size_rejects_oversized_file():
    with pytest.raises(UploadValidationError):
        validate_upload_size(MAX_UPLOAD_BYTES + 1)


def test_validate_upload_size_rejects_empty_file():
    with pytest.raises(UploadValidationError):
        validate_upload_size(0)


def test_save_page_bytes_writes_file_with_generated_name(tmp_path: Path):
    path = save_page_bytes(_fake_jpeg_bytes(), tmp_path, content_type="image/jpeg")

    assert path.exists()
    assert path.name == "page_1.jpg"


def test_save_page_bytes_numbers_successive_uploads(tmp_path: Path):
    first = save_page_bytes(_fake_jpeg_bytes(), tmp_path, content_type="image/jpeg")
    second = save_page_bytes(_fake_jpeg_bytes(), tmp_path, content_type="image/png")

    assert first.name == "page_1.jpg"
    assert second.name == "page_2.png"


def test_save_page_bytes_rejects_unsupported_content_type(tmp_path: Path):
    with pytest.raises(UploadValidationError):
        save_page_bytes(_fake_jpeg_bytes(), tmp_path, content_type="application/pdf")


def test_save_page_bytes_rejects_executable_content_type(tmp_path: Path):
    with pytest.raises(UploadValidationError):
        save_page_bytes(b"MZ\x90\x00", tmp_path, content_type="application/x-msdownload")


def test_save_page_bytes_rejects_oversized_content(tmp_path: Path):
    with pytest.raises(UploadValidationError):
        save_page_bytes(b"x" * (MAX_UPLOAD_BYTES + 1), tmp_path, content_type="image/jpeg")


def test_save_local_page_file_ignores_original_filename(tmp_path: Path):
    source = tmp_path / "my original photo!! (final) FINAL2.JPG"
    source.write_bytes(_fake_jpeg_bytes())

    uploads_dir = tmp_path / "uploads"
    saved = save_local_page_file(source, uploads_dir)

    assert saved.name == "page_1.jpg"  # original filename not trusted/reused
    assert saved.parent == uploads_dir


def test_save_local_page_file_rejects_missing_file(tmp_path: Path):
    with pytest.raises(UploadValidationError):
        save_local_page_file(tmp_path / "does_not_exist.jpg", tmp_path / "uploads")


def test_save_local_page_file_rejects_oversized_file(tmp_path: Path):
    source = tmp_path / "big.jpg"
    source.write_bytes(b"x" * 100)

    with pytest.raises(UploadValidationError):
        save_local_page_file(source, tmp_path / "uploads", max_bytes=50)
