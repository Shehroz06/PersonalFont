from pathlib import Path

import numpy as np
import pytest

from pipeline.alignment.align import align_page_to_template
from pipeline.segmentation.config import SegmentationConfig
from pipeline.segmentation.errors import SegmentationError
from pipeline.segmentation.extract import extract_glyphs
from tests.alignment_helpers import simulate_photo
from tests.segmentation_helpers import build_template_document_with_elements, render_template_page_with_ink

DPI = 100.0


def test_extract_glyphs_creates_one_file_per_element(tmp_path: Path):
    document = build_template_document_with_elements(num_pages=1)
    page = document.pages[0]
    image = render_template_page_with_ink(document, page, DPI)

    results = extract_glyphs(
        image=image,
        page=page,
        page_height_pt=document.page_size.height,
        dpi=DPI,
        job_id="testjob",
        output_dir=tmp_path,
        source_image="page_1.png",
        extraction_confidence=0.95,
    )

    assert len(results) == len(page.elements)
    for glyph, element in zip(results, page.elements):
        expected_path = tmp_path / f"{element.id}.png"
        assert expected_path.exists()
        assert glyph.image_path == str(expected_path)
        assert glyph.character == element.character
        assert glyph.character_id == element.id
        assert glyph.job_id == "testjob"
        assert glyph.page == page.page
        assert glyph.extraction_confidence == 0.95


def test_extract_glyphs_filenames_use_character_id_not_raw_character(tmp_path: Path):
    document = build_template_document_with_elements(num_pages=1)
    page = document.pages[0]
    image = render_template_page_with_ink(document, page, DPI)

    extract_glyphs(
        image=image,
        page=page,
        page_height_pt=document.page_size.height,
        dpi=DPI,
        job_id="testjob",
        output_dir=tmp_path,
        source_image="page_1.png",
        extraction_confidence=1.0,
    )

    saved = {p.name for p in tmp_path.glob("*.png")}
    assert saved == {f"{el.id}.png" for el in page.elements}
    assert "A.png" not in saved  # raw character is not used as the filename


def test_extract_glyphs_crop_contains_ink(tmp_path: Path):
    document = build_template_document_with_elements(num_pages=1)
    page = document.pages[0]
    image = render_template_page_with_ink(document, page, DPI)

    results = extract_glyphs(
        image=image,
        page=page,
        page_height_pt=document.page_size.height,
        dpi=DPI,
        job_id="testjob",
        output_dir=tmp_path,
        source_image="page_1.png",
        extraction_confidence=1.0,
    )

    for glyph in results:
        crop = image[
            glyph.crop_box.y : glyph.crop_box.y + glyph.crop_box.height,
            glyph.crop_box.x : glyph.crop_box.x + glyph.crop_box.width,
        ]
        assert crop.min() < 50  # the drawn ink square is present in the crop


def test_extract_glyphs_padding_expands_crop_box(tmp_path: Path):
    document = build_template_document_with_elements(num_pages=1)
    page = document.pages[0]
    image = render_template_page_with_ink(document, page, DPI)

    no_padding = extract_glyphs(
        image=image,
        page=page,
        page_height_pt=document.page_size.height,
        dpi=DPI,
        job_id="testjob",
        output_dir=tmp_path / "no_padding",
        source_image="page_1.png",
        extraction_confidence=1.0,
        config=SegmentationConfig(padding_px=0),
    )
    padded = extract_glyphs(
        image=image,
        page=page,
        page_height_pt=document.page_size.height,
        dpi=DPI,
        job_id="testjob",
        output_dir=tmp_path / "padded",
        source_image="page_1.png",
        extraction_confidence=1.0,
        config=SegmentationConfig(padding_px=10),
    )

    for base, pad in zip(no_padding, padded):
        assert pad.crop_box.width == base.crop_box.width + 20
        assert pad.crop_box.height == base.crop_box.height + 20


def test_extract_glyphs_raises_when_crop_entirely_out_of_bounds():
    document = build_template_document_with_elements(num_pages=1)
    page = document.pages[0]
    tiny_image = np.full((5, 5), 255, dtype=np.uint8)

    with pytest.raises(SegmentationError):
        extract_glyphs(
            image=tiny_image,
            page=page,
            page_height_pt=document.page_size.height,
            dpi=DPI,
            job_id="testjob",
            output_dir=Path("/tmp/unused"),
            source_image="page_1.png",
            extraction_confidence=1.0,
        )


def test_align_then_extract_end_to_end(tmp_path: Path):
    document = build_template_document_with_elements(num_pages=1)
    page = document.pages[0]
    template_image = render_template_page_with_ink(document, page, DPI)

    canvas_size = (template_image.shape[1] + 120, template_image.shape[0] + 120)
    photo = simulate_photo(template_image, canvas_size, angle_deg=5.0, translation=(30, 20))

    alignment = align_page_to_template(photo, document, dpi=DPI)
    results = extract_glyphs(
        image=alignment.aligned_image,
        page=alignment.page,
        page_height_pt=document.page_size.height,
        dpi=DPI,
        job_id="testjob",
        output_dir=tmp_path,
        source_image="photo.png",
        extraction_confidence=alignment.confidence,
    )

    assert len(results) == 2
    for glyph in results:
        assert Path(glyph.image_path).exists()
        crop = alignment.aligned_image[
            glyph.crop_box.y : glyph.crop_box.y + glyph.crop_box.height,
            glyph.crop_box.x : glyph.crop_box.x + glyph.crop_box.width,
        ]
        assert crop.min() < 80  # ink survived alignment + extraction
