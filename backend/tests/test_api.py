from pathlib import Path

import cv2
import pytest
from fastapi.testclient import TestClient
from fontTools.ttLib import TTFont

from app.api.deps import get_jobs_root, get_templates_root
from app.main import create_app
from tests.integration_helpers import render_clean_template_page, simulate_page_photo

REPO_TEMPLATES = Path(__file__).resolve().parent.parent.parent / "templates"
DPI = 150.0
CHARACTERS = {"H", "I", "T", "O", "L"}


@pytest.fixture
def client(tmp_path: Path):
    app = create_app()
    app.dependency_overrides[get_jobs_root] = lambda: tmp_path / "jobs"
    app.dependency_overrides[get_templates_root] = lambda: REPO_TEMPLATES
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_photo_bytes(tmp_path: Path) -> bytes:
    from app.template_gen.loader import load_template_document

    document = load_template_document(REPO_TEMPLATES / "template_v1.json")
    page = document.pages[0]
    clean_page = render_clean_template_page(document, page, dpi=DPI, characters_to_draw=CHARACTERS)
    photo = simulate_page_photo(clean_page, canvas_size=(clean_page.shape[1] + 300, clean_page.shape[0] + 300))
    ok, encoded = cv2.imencode(".jpg", photo)
    assert ok
    return encoded.tobytes()


# --- health --------------------------------------------------------------


def test_health_check(client: TestClient):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# --- templates -------------------------------------------------------------


def test_list_templates_includes_template_v1(client: TestClient):
    response = client.get("/api/templates")

    assert response.status_code == 200
    ids = {t["template_id"] for t in response.json()}
    assert "template_v1" in ids


def test_get_template_returns_full_document(client: TestClient):
    response = client.get("/api/templates/template_v1")

    assert response.status_code == 200
    body = response.json()
    assert body["template_id"] == "template_v1"
    assert len(body["pages"]) >= 1


def test_get_template_404_for_unknown_id(client: TestClient):
    response = client.get("/api/templates/does_not_exist")

    assert response.status_code == 404


def test_get_template_rejects_path_traversal_id(client: TestClient):
    response = client.get("/api/templates/..%2F..%2Fetc")

    assert response.status_code in (400, 404)


def test_download_template_pdf_returns_pdf(client: TestClient):
    response = client.get("/api/templates/template_v1/pdf")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


def test_download_template_pdf_404_for_unknown_id(client: TestClient):
    response = client.get("/api/templates/does_not_exist/pdf")

    assert response.status_code == 404


# --- job creation ----------------------------------------------------------


def test_create_job_returns_created_status(client: TestClient):
    response = client.post("/api/jobs", json={"template_id": "template_v1"})

    assert response.status_code == 201
    body = response.json()
    assert body["state"] == "created"
    assert body["template_id"] == "template_v1"
    assert len(body["job_id"]) == 32


def test_create_job_404_for_unknown_template(client: TestClient):
    response = client.post("/api/jobs", json={"template_id": "not_a_real_template"})

    assert response.status_code == 404


def test_status_404_for_unknown_job(client: TestClient):
    response = client.get("/api/jobs/00000000000000000000000000000000/status")

    assert response.status_code == 404


# --- page upload -------------------------------------------------------------


def test_upload_pages_updates_status(client: TestClient, sample_photo_bytes: bytes):
    job_id = client.post("/api/jobs", json={}).json()["job_id"]

    response = client.post(
        f"/api/jobs/{job_id}/pages",
        files={"files": ("photo.jpg", sample_photo_bytes, "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["pages_uploaded"] == 1
    assert body["filenames"] == ["page_1.jpg"]  # original filename not used

    status = client.get(f"/api/jobs/{job_id}/status").json()
    assert status["state"] == "uploading"
    assert status["pages_uploaded"] == 1


def test_upload_pages_rejects_wrong_content_type(client: TestClient):
    job_id = client.post("/api/jobs", json={}).json()["job_id"]

    response = client.post(
        f"/api/jobs/{job_id}/pages",
        files={"files": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")},
    )

    assert response.status_code == 400


def test_upload_pages_404_for_unknown_job(client: TestClient, sample_photo_bytes: bytes):
    response = client.post(
        "/api/jobs/00000000000000000000000000000000/pages",
        files={"files": ("photo.jpg", sample_photo_bytes, "image/jpeg")},
    )

    assert response.status_code == 404


def test_upload_pages_rejects_after_processing_started(client: TestClient, sample_photo_bytes: bytes):
    job_id = client.post("/api/jobs", json={}).json()["job_id"]
    client.post(f"/api/jobs/{job_id}/pages", files={"files": ("p.jpg", sample_photo_bytes, "image/jpeg")})
    client.post(f"/api/jobs/{job_id}/process", json={})

    response = client.post(
        f"/api/jobs/{job_id}/pages",
        files={"files": ("p2.jpg", sample_photo_bytes, "image/jpeg")},
    )

    assert response.status_code == 409


# --- processing --------------------------------------------------------------


def test_process_without_pages_returns_409(client: TestClient):
    job_id = client.post("/api/jobs", json={}).json()["job_id"]

    response = client.post(f"/api/jobs/{job_id}/process", json={})

    assert response.status_code == 409


def test_process_404_for_unknown_job(client: TestClient):
    response = client.post("/api/jobs/00000000000000000000000000000000/process", json={})

    assert response.status_code == 404


def test_validation_and_download_unavailable_before_processing(client: TestClient, sample_photo_bytes: bytes):
    job_id = client.post("/api/jobs", json={}).json()["job_id"]
    client.post(f"/api/jobs/{job_id}/pages", files={"files": ("p.jpg", sample_photo_bytes, "image/jpeg")})

    assert client.get(f"/api/jobs/{job_id}/validation").status_code == 409
    assert client.get(f"/api/jobs/{job_id}/download").status_code == 409
    assert client.get(f"/api/jobs/{job_id}/preview").status_code == 409


# --- full round trip ----------------------------------------------------------


def test_full_flow_create_upload_process_status_validation_download(client: TestClient, sample_photo_bytes: bytes):
    create_response = client.post("/api/jobs", json={"template_id": "template_v1"})
    assert create_response.status_code == 201
    job_id = create_response.json()["job_id"]

    upload_response = client.post(
        f"/api/jobs/{job_id}/pages",
        files={"files": ("photo.jpg", sample_photo_bytes, "image/jpeg")},
    )
    assert upload_response.status_code == 200

    process_response = client.post(
        f"/api/jobs/{job_id}/process",
        json={"family_name": "API Test Font", "creator": "Test Suite", "version": "2.0"},
    )
    assert process_response.status_code == 202

    # TestClient runs BackgroundTasks synchronously before the request
    # returns, so the job should already be finished by now.
    status = client.get(f"/api/jobs/{job_id}/status").json()
    assert status["state"] == "completed"
    assert status["valid_glyph_count"] is not None
    assert status["valid_glyph_count"] > 0

    validation_response = client.get(f"/api/jobs/{job_id}/validation")
    assert validation_response.status_code == 200
    validations = validation_response.json()
    assert len(validations) > 0
    assert any(v["valid"] and v["character"] in CHARACTERS for v in validations)

    download_response = client.get(f"/api/jobs/{job_id}/download", params={"format": "ttf"})
    assert download_response.status_code == 200
    assert download_response.headers["content-type"] in ("font/ttf", "application/octet-stream")
    assert len(download_response.content) > 0

    import io

    font = TTFont(io.BytesIO(download_response.content))
    cmap = font.getBestCmap()
    assert any(ord(ch) in cmap for ch in CHARACTERS)
    font.close()

    otf_response = client.get(f"/api/jobs/{job_id}/download", params={"format": "otf"})
    assert otf_response.status_code == 200
    assert len(otf_response.content) > 0

    # default download (no format) is the full spec §13 package
    import zipfile

    zip_response = client.get(f"/api/jobs/{job_id}/download")
    assert zip_response.status_code == 200
    assert zip_response.headers["content-type"] in ("application/zip", "application/octet-stream")
    with zipfile.ZipFile(io.BytesIO(zip_response.content)) as zf:
        names = set(zf.namelist())
    assert "metadata.json" in names
    assert "README.txt" in names
    assert "glyphs.zip" in names
    assert any(name.endswith(".ttf") for name in names)
    assert any(name.endswith(".otf") for name in names)

    preview_png_response = client.get(f"/api/jobs/{job_id}/preview", params={"format": "png"})
    assert preview_png_response.status_code == 200
    assert preview_png_response.headers["content-type"] in ("image/png", "application/octet-stream")
    assert len(preview_png_response.content) > 0

    preview_pdf_response = client.get(f"/api/jobs/{job_id}/preview", params={"format": "pdf"})
    assert preview_pdf_response.status_code == 200
    assert preview_pdf_response.content.startswith(b"%PDF-")


def test_download_rejects_invalid_format(client: TestClient, sample_photo_bytes: bytes):
    job_id = client.post("/api/jobs", json={}).json()["job_id"]
    client.post(f"/api/jobs/{job_id}/pages", files={"files": ("p.jpg", sample_photo_bytes, "image/jpeg")})
    client.post(f"/api/jobs/{job_id}/process", json={})

    response = client.get(f"/api/jobs/{job_id}/download", params={"format": "exe"})

    assert response.status_code == 400


def test_preview_rejects_invalid_format(client: TestClient, sample_photo_bytes: bytes):
    job_id = client.post("/api/jobs", json={}).json()["job_id"]
    client.post(f"/api/jobs/{job_id}/pages", files={"files": ("p.jpg", sample_photo_bytes, "image/jpeg")})
    client.post(f"/api/jobs/{job_id}/process", json={})

    response = client.get(f"/api/jobs/{job_id}/preview", params={"format": "svg"})

    assert response.status_code == 400


def test_preview_404_for_unknown_job(client: TestClient):
    response = client.get("/api/jobs/00000000000000000000000000000000/preview")

    assert response.status_code == 404


# --- character set -----------------------------------------------------------


def test_character_set_returns_full_ordered_list(client: TestClient):
    response = client.get("/api/character-set")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 76
    assert body[0] == {"character_id": "uppercase_A", "character": "A"}
    assert body[-1]["character_id"] == "punctuation_underscore"
