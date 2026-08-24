import io
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

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
def sample_photo_bytes() -> bytes:
    from app.template_gen.loader import load_template_document

    document = load_template_document(REPO_TEMPLATES / "template_v1.json")
    page = document.pages[0]
    clean_page = render_clean_template_page(document, page, dpi=DPI, characters_to_draw=CHARACTERS)
    photo = simulate_page_photo(clean_page, canvas_size=(clean_page.shape[1] + 300, clean_page.shape[0] + 300))
    ok, encoded = cv2.imencode(".jpg", photo)
    assert ok
    return encoded.tobytes()


def _completed_job_id(client: TestClient, sample_photo_bytes: bytes) -> str:
    job_id = client.post("/api/jobs", json={"template_id": "template_v1"}).json()["job_id"]
    client.post(f"/api/jobs/{job_id}/pages", files={"files": ("p.jpg", sample_photo_bytes, "image/jpeg")})
    client.post(f"/api/jobs/{job_id}/process", json={})
    return job_id


def _marks_grid_jpeg_bytes(count: int, cols: int = 8) -> bytes:
    rows = (count + cols - 1) // cols
    cell = 60
    image = np.full((rows * cell + cell, cols * cell + cell, 3), 255, dtype=np.uint8)
    for i in range(count):
        row, col = divmod(i, cols)
        cx = cell // 2 + cell + col * cell
        cy = cell // 2 + cell + row * cell
        half = 15
        cv2.rectangle(image, (cx - half, cy - half), (cx + half, cy + half), (0, 0, 0), -1)
    ok, encoded = cv2.imencode(".jpg", image)
    assert ok
    return encoded.tobytes()


def test_rewrite_list_404_for_unknown_job(client: TestClient):
    response = client.get("/api/jobs/00000000000000000000000000000000/rewrite-list")
    assert response.status_code == 404


def test_rewrite_list_409_before_job_completes(client: TestClient):
    job_id = client.post("/api/jobs", json={}).json()["job_id"]
    response = client.get(f"/api/jobs/{job_id}/rewrite-list")
    assert response.status_code == 409


def test_rewrite_list_returns_only_invalid_characters(client: TestClient, sample_photo_bytes: bytes):
    job_id = _completed_job_id(client, sample_photo_bytes)
    validations = client.get(f"/api/jobs/{job_id}/validation").json()
    valid_ids = {v["character_id"] for v in validations if v["valid"]}

    response = client.get(f"/api/jobs/{job_id}/rewrite-list")

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == job_id
    rewrite_ids = {c["character_id"] for c in body["characters"]}
    assert rewrite_ids.isdisjoint(valid_ids)  # already-valid characters aren't in the rewrite list
    assert len(rewrite_ids) == len(validations) - len(valid_ids)


def test_rewrite_409_before_job_completes(client: TestClient):
    job_id = client.post("/api/jobs", json={}).json()["job_id"]
    image_bytes = _marks_grid_jpeg_bytes(1)

    response = client.post(f"/api/jobs/{job_id}/rewrite", files={"file": ("r.jpg", image_bytes, "image/jpeg")})

    assert response.status_code == 409


def test_rewrite_full_round_trip_increases_valid_count(client: TestClient, sample_photo_bytes: bytes):
    job_id = _completed_job_id(client, sample_photo_bytes)
    status_before = client.get(f"/api/jobs/{job_id}/status").json()

    rewrite_list = client.get(f"/api/jobs/{job_id}/rewrite-list").json()["characters"]
    image_bytes = _marks_grid_jpeg_bytes(len(rewrite_list))

    response = client.post(f"/api/jobs/{job_id}/rewrite", files={"file": ("r.jpg", image_bytes, "image/jpeg")})
    assert response.status_code == 202

    # TestClient runs BackgroundTasks synchronously before returning.
    status_after = client.get(f"/api/jobs/{job_id}/status").json()
    assert status_after["state"] == "completed"
    assert status_after["valid_glyph_count"] > status_before["valid_glyph_count"]

    # The regenerated font is still downloadable afterwards.
    download = client.get(f"/api/jobs/{job_id}/download", params={"format": "ttf"})
    assert download.status_code == 200
    assert len(download.content) > 0


def test_rewrite_rejects_mismatched_mark_count(client: TestClient, sample_photo_bytes: bytes):
    job_id = _completed_job_id(client, sample_photo_bytes)
    rewrite_list = client.get(f"/api/jobs/{job_id}/rewrite-list").json()["characters"]
    image_bytes = _marks_grid_jpeg_bytes(len(rewrite_list) - 1)  # one short

    response = client.post(f"/api/jobs/{job_id}/rewrite", files={"file": ("r.jpg", image_bytes, "image/jpeg")})
    assert response.status_code == 202

    status_after = client.get(f"/api/jobs/{job_id}/status").json()
    assert status_after["state"] == "failed"
    assert status_after["error"]


def test_rewrite_rejects_wrong_content_type(client: TestClient, sample_photo_bytes: bytes):
    job_id = _completed_job_id(client, sample_photo_bytes)

    response = client.post(
        f"/api/jobs/{job_id}/rewrite", files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")}
    )

    assert response.status_code == 400


def test_exclude_409_before_job_completes(client: TestClient):
    job_id = client.post("/api/jobs", json={}).json()["job_id"]

    response = client.post(f"/api/jobs/{job_id}/exclude", json={"character_ids": ["uppercase_A"]})

    assert response.status_code == 409


def test_exclude_400_for_empty_character_list(client: TestClient, sample_photo_bytes: bytes):
    job_id = _completed_job_id(client, sample_photo_bytes)

    response = client.post(f"/api/jobs/{job_id}/exclude", json={"character_ids": []})

    assert response.status_code == 400


def test_exclude_marks_character_invalid_and_regenerates_font(client: TestClient, sample_photo_bytes: bytes):
    job_id = _completed_job_id(client, sample_photo_bytes)
    validations_before = client.get(f"/api/jobs/{job_id}/validation").json()
    valid_before = [v for v in validations_before if v["valid"]]
    assert valid_before, "fixture must produce at least one valid character"
    to_exclude = valid_before[0]["character_id"]

    response = client.post(f"/api/jobs/{job_id}/exclude", json={"character_ids": [to_exclude]})
    assert response.status_code == 202

    status_after = client.get(f"/api/jobs/{job_id}/status").json()
    assert status_after["state"] == "completed"

    validations_after = client.get(f"/api/jobs/{job_id}/validation").json()
    excluded = next(v for v in validations_after if v["character_id"] == to_exclude)
    assert excluded["valid"] is False
    assert excluded["warnings"] == ["Manually excluded"]

    download = client.get(f"/api/jobs/{job_id}/download", params={"format": "ttf"})
    assert download.status_code == 200
    assert len(download.content) > 0
