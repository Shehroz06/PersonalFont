"""Required integration test (spec §19):

    sample pages -> preprocessing -> segmentation -> validation ->
    normalization -> SVG -> TTF/OTF

(template alignment also runs between preprocessing and segmentation,
since it's a required step in the actual pipeline architecture — spec
§5 — not just a simplification in §19's summary diagram. Preview
generation and packaging, spec §12-13, also run as part of
run_pipeline now — the assertions below check those outputs too, since
this is the one test that exercises the entire real pipeline.)

Unlike the other phases' tests, this one deliberately does *not* start
from a pre-binarized/pre-aligned shortcut: it builds a synthetic
photograph in standard scan polarity (white paper, black ink) against a
noisy background, so it exercises real Phase 3 page detection,
perspective correction, thresholding and deskew — not just the stages
downstream of them.
"""

from pathlib import Path

import cv2
from fontTools.ttLib import TTFont

from app.services.jobs import generate_job_id, resolve_job_paths
from app.services.pipeline_runner import run_pipeline
from app.services.uploads import save_local_page_file
from app.template_gen.loader import load_template_document
from pipeline.preprocessing.config import PreprocessingConfig
from tests.integration_helpers import render_clean_template_page, simulate_page_photo

TEMPLATE_PATH = Path(__file__).resolve().parent.parent.parent / "templates" / "template_v1.json"
DPI = 150.0
CHARACTERS = {"H", "I", "T", "O", "L"}


def test_full_pipeline_produces_a_valid_font(tmp_path: Path):
    document = load_template_document(TEMPLATE_PATH)
    page = document.pages[0]

    clean_page = render_clean_template_page(document, page, dpi=DPI, characters_to_draw=CHARACTERS)
    photo = simulate_page_photo(clean_page, canvas_size=(clean_page.shape[1] + 300, clean_page.shape[0] + 300))

    photo_path = tmp_path / "page_1.jpg"
    cv2.imwrite(str(photo_path), photo)

    job_id = generate_job_id()
    job_paths = resolve_job_paths(tmp_path / "jobs", job_id)
    job_paths.ensure_dirs()
    saved_path = save_local_page_file(photo_path, job_paths.uploads)

    result = run_pipeline(
        job_id,
        [saved_path],
        document,
        job_paths,
        preprocessing_config=PreprocessingConfig(working_dpi=DPI),
    )

    # preprocessing + alignment + segmentation
    assert any(p.succeeded for p in result.pages)
    successful_page = next(p for p in result.pages if p.succeeded)
    assert successful_page.template_page == 1
    assert successful_page.glyphs_extracted > 0

    # validation
    assert len(result.validations) == successful_page.glyphs_extracted
    valid_results = [v for v in result.validations if v.valid]
    assert any(v.character in CHARACTERS for v in valid_results)

    # normalization -> SVG -> TTF/OTF: a real, loadable font was produced
    assert result.font is not None
    ttf_path = Path(result.font.ttf_path)
    otf_path = Path(result.font.otf_path)
    assert ttf_path.exists() and ttf_path.stat().st_size > 0
    assert otf_path.exists() and otf_path.stat().st_size > 0

    font = TTFont(str(ttf_path))
    cmap = font.getBestCmap()
    # at least some of what we actually drew made it all the way through
    assert any(ord(ch) in cmap for ch in CHARACTERS)
    font.close()

    otf_font = TTFont(str(otf_path))
    assert set(otf_font.getGlyphOrder()) == set(font.getGlyphOrder())
    otf_font.close()

    # preview + packaging: real preview media and a downloadable package
    preview_png = Path(result.preview_png_path)
    preview_pdf = Path(result.preview_pdf_path)
    assert preview_png.exists() and preview_png.stat().st_size > 0
    assert preview_pdf.read_bytes().startswith(b"%PDF-")

    package_zip = Path(result.package.zip_path)
    assert package_zip.exists()
    import zipfile

    with zipfile.ZipFile(package_zip) as zf:
        names = set(zf.namelist())
    assert "metadata.json" in names
    assert "README.txt" in names
    assert "glyphs.zip" in names
    assert any(name.endswith(".ttf") for name in names)
    assert any(name.endswith(".otf") for name in names)

    assert Path(result.log_path).exists()
