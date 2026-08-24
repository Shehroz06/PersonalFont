from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_jobs_root, get_templates_root
from app.main import create_app
from app.template_gen.character_set import get_character_set

REPO_TEMPLATES = Path(__file__).resolve().parent.parent.parent / "templates"


@pytest.fixture
def client(tmp_path: Path):
    app = create_app()
    app.dependency_overrides[get_jobs_root] = lambda: tmp_path / "jobs"
    app.dependency_overrides[get_templates_root] = lambda: REPO_TEMPLATES
    with TestClient(app) as test_client:
        yield test_client


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


def test_create_freeform_job_full_round_trip(client: TestClient):
    total = len(get_character_set())
    image_bytes = _marks_grid_jpeg_bytes(total)

    response = client.post(
        "/api/jobs/freeform",
        files={"file": ("marks.jpg", image_bytes, "image/jpeg")},
        data={"family_name": "Freeform Test Font"},
    )

    assert response.status_code == 202
    job_id = response.json()["job_id"]
    assert response.json()["template_id"] == "freeform"

    # TestClient runs BackgroundTasks synchronously before returning.
    status = client.get(f"/api/jobs/{job_id}/status").json()
    assert status["state"] == "completed"
    assert status["valid_glyph_count"] > 0

    download = client.get(f"/api/jobs/{job_id}/download", params={"format": "ttf"})
    assert download.status_code == 200
    assert len(download.content) > 0


def test_create_freeform_job_fails_on_mismatched_mark_count(client: TestClient):
    total = len(get_character_set())
    image_bytes = _marks_grid_jpeg_bytes(total - 1)  # one short

    response = client.post("/api/jobs/freeform", files={"file": ("marks.jpg", image_bytes, "image/jpeg")})

    assert response.status_code == 202
    job_id = response.json()["job_id"]

    status = client.get(f"/api/jobs/{job_id}/status").json()
    assert status["state"] == "failed"
    assert status["error"]


def test_create_freeform_job_rejects_wrong_content_type(client: TestClient):
    response = client.post(
        "/api/jobs/freeform", files={"file": ("doc.pdf", b"%PDF-1.4 fake", "application/pdf")}
    )

    assert response.status_code == 400
