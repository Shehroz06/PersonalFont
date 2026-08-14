from pathlib import Path

import pytest

from app.services.jobs import JobPaths, generate_job_id, is_valid_job_id, resolve_job_paths


def test_generate_job_id_is_valid():
    job_id = generate_job_id()

    assert is_valid_job_id(job_id)
    assert len(job_id) == 32


def test_generate_job_id_is_unique():
    assert generate_job_id() != generate_job_id()


@pytest.mark.parametrize(
    "bad_id",
    [
        "../../etc/passwd",
        "../escape",
        "not-a-uuid",
        "",
        "12345",
        "UPPERCASE1234567890ABCDEF123456",
    ],
)
def test_invalid_job_ids_are_rejected(bad_id: str):
    assert not is_valid_job_id(bad_id)


def test_resolve_job_paths_raises_for_path_traversal_attempt(tmp_path: Path):
    with pytest.raises(ValueError):
        resolve_job_paths(tmp_path, "../../etc")


def test_resolve_job_paths_stays_inside_jobs_root(tmp_path: Path):
    job_id = generate_job_id()

    paths = resolve_job_paths(tmp_path, job_id)

    assert paths.root == tmp_path / job_id
    assert paths.root.is_relative_to(tmp_path)


def test_job_paths_ensure_dirs_creates_all_subdirectories(tmp_path: Path):
    paths = JobPaths(root=tmp_path / "somejob")

    paths.ensure_dirs()

    for subdir in (paths.uploads, paths.processed, paths.glyphs, paths.svg, paths.font, paths.preview, paths.logs):
        assert subdir.is_dir()


def test_different_jobs_get_isolated_directories(tmp_path: Path):
    job_a = resolve_job_paths(tmp_path, generate_job_id())
    job_b = resolve_job_paths(tmp_path, generate_job_id())

    assert job_a.root != job_b.root
