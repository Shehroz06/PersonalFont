from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from pipeline.font_generation.build import generate_fonts
from pipeline.preview.config import PreviewConfig
from pipeline.preview.errors import PreviewError
from pipeline.preview.render import generate_preview_image, generate_preview_pdf
from tests.font_generation_helpers import build_sample_glyphs


@pytest.fixture(scope="module")
def sample_font(tmp_path_factory) -> Path:
    base = tmp_path_factory.mktemp("preview_font")
    glyphs = build_sample_glyphs(base / "svg")
    result = generate_fonts(glyphs, base / "font")
    return Path(result.ttf_path)


def test_generate_preview_image_creates_readable_png(tmp_path: Path, sample_font: Path):
    output_path = tmp_path / "preview.png"

    result_path = generate_preview_image(sample_font, output_path)

    assert result_path == output_path
    assert output_path.exists()

    image = Image.open(output_path)
    assert image.size == (PreviewConfig().image_width, PreviewConfig().image_height)


def test_generate_preview_image_actually_draws_something(tmp_path: Path, sample_font: Path):
    output_path = tmp_path / "preview.png"
    generate_preview_image(sample_font, output_path)

    pixels = np.array(Image.open(output_path).convert("L"))
    assert pixels.min() < 250  # some dark (text) pixels exist, not a blank white image


def test_generate_preview_image_respects_custom_config(tmp_path: Path, sample_font: Path):
    output_path = tmp_path / "preview.png"
    config = PreviewConfig(image_width=300, image_height=150, sample_lines=("Hello",))

    generate_preview_image(sample_font, output_path, config)

    assert Image.open(output_path).size == (300, 150)


def test_generate_preview_image_raises_for_invalid_font(tmp_path: Path):
    with pytest.raises(PreviewError):
        generate_preview_image(tmp_path / "does_not_exist.ttf", tmp_path / "preview.png")


def test_generate_preview_pdf_creates_valid_pdf(tmp_path: Path, sample_font: Path):
    output_path = tmp_path / "preview.pdf"

    result_path = generate_preview_pdf(sample_font, output_path, "My Test Font")

    assert result_path == output_path
    assert output_path.read_bytes().startswith(b"%PDF-")
    assert output_path.stat().st_size > 0


def test_generate_preview_pdf_raises_for_invalid_font(tmp_path: Path):
    with pytest.raises(PreviewError):
        generate_preview_pdf(tmp_path / "does_not_exist.ttf", tmp_path / "preview.pdf", "My Test Font")


def test_generate_preview_pdf_can_be_called_multiple_times_in_one_process(tmp_path: Path, sample_font: Path):
    # Regression guard: reportlab's font registry is process-global: a
    # fixed/reused font name across calls (e.g. for different jobs
    # handled by the same long-lived server process) could collide.
    generate_preview_pdf(sample_font, tmp_path / "one.pdf", "Font One")
    generate_preview_pdf(sample_font, tmp_path / "two.pdf", "Font Two")

    assert (tmp_path / "one.pdf").exists()
    assert (tmp_path / "two.pdf").exists()
