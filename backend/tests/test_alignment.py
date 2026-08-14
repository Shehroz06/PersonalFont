import numpy as np
import pytest

from app.template_gen.coordinates import marker_corners_px, page_size_px
from pipeline.alignment.align import align_page_to_template
from pipeline.alignment.confidence import compute_alignment_confidence
from pipeline.alignment.errors import AlignmentError
from pipeline.alignment.homography import estimate_homography
from pipeline.alignment.marker_detection import detect_markers
from tests.alignment_helpers import (
    blank_out_region,
    build_minimal_template_document,
    render_template_page_image,
    simulate_photo,
)

DPI = 100.0


# --- marker_detection ---------------------------------------------------


def test_detect_markers_finds_all_four_page_markers():
    document = build_minimal_template_document(num_pages=1)
    page = document.pages[0]
    image = render_template_page_image(document, page, DPI)

    detected = detect_markers(image)

    assert {m.marker_id for m in detected} == {m.marker_id for m in page.markers}


def test_detect_markers_finds_markers_on_inverted_ink255_image():
    # Regression test: pipeline.preprocessing.thresholding's convention is
    # ink/marker=255, background=0 — the opposite polarity from a normal
    # scan. Real preprocessed pages reach alignment in this form, but
    # ArUco's default detector parameters only look for the standard
    # dark-on-light polarity and silently find nothing on this convention
    # without pipeline.alignment.marker_detection setting
    # detectInvertedMarker.
    document = build_minimal_template_document(num_pages=1)
    page = document.pages[0]
    image = 255 - render_template_page_image(document, page, DPI)

    detected = detect_markers(image)

    assert {m.marker_id for m in detected} == {m.marker_id for m in page.markers}


def test_detect_markers_returns_empty_list_for_blank_image():
    blank = np.full((200, 200), 255, dtype=np.uint8)

    assert detect_markers(blank) == []


# --- homography / confidence ------------------------------------------------


def test_estimate_homography_recovers_identity_for_unmoved_page():
    document = build_minimal_template_document(num_pages=1)
    page = document.pages[0]
    image = render_template_page_image(document, page, DPI)

    detected = detect_markers(image)
    expected = {m.marker_id: marker_corners_px(m, document.page_size.height, DPI) for m in page.markers}

    homography, mean_error = estimate_homography(detected, expected)

    # detectInvertedMarker (needed so alignment works on this pipeline's
    # ink=255 binary convention, not just normal-polarity images — see
    # marker_detection.py) costs a documented ~1px of corner precision
    # even on normal-polarity input; still well within what
    # align_page_to_template's default thresholds accept.
    assert mean_error < 2.0
    assert np.allclose(homography / homography[2, 2], np.eye(3), atol=0.1)


def test_confidence_drops_with_fewer_markers_or_higher_error():
    full = compute_alignment_confidence(4, 4, mean_reprojection_error_px=0.0, max_reprojection_error_px=8.0)
    partial_coverage = compute_alignment_confidence(2, 4, mean_reprojection_error_px=0.0, max_reprojection_error_px=8.0)
    poor_fit = compute_alignment_confidence(4, 4, mean_reprojection_error_px=6.0, max_reprojection_error_px=8.0)

    assert full == 1.0
    assert partial_coverage < full
    assert poor_fit < full


# --- align_page_to_template (integration-lite) -------------------------------


def test_align_recovers_rotated_translated_page():
    document = build_minimal_template_document(num_pages=1)
    page = document.pages[0]
    template_image = render_template_page_image(document, page, DPI)

    canvas_size = (template_image.shape[1] + 150, template_image.shape[0] + 150)
    photo = simulate_photo(template_image, canvas_size, angle_deg=9.0, scale=0.9, translation=(40, 30))

    result = align_page_to_template(photo, document, dpi=DPI)

    assert result.page.page == 1
    assert result.confidence > 0.7
    assert result.matched_markers == 4
    expected_size = page_size_px(document.page_size.width, document.page_size.height, DPI)
    assert result.aligned_image.shape[:2] == (expected_size[1], expected_size[0])

    redetected = detect_markers(result.aligned_image)
    assert {m.marker_id for m in redetected} == {m.marker_id for m in page.markers}


def test_align_identifies_correct_page_among_several():
    document = build_minimal_template_document(num_pages=2)
    page_2 = document.pages[1]
    template_image = render_template_page_image(document, page_2, DPI)
    canvas_size = (template_image.shape[1] + 100, template_image.shape[0] + 100)
    photo = simulate_photo(template_image, canvas_size, angle_deg=3.0, translation=(20, 20))

    result = align_page_to_template(photo, document, dpi=DPI)

    assert result.page.page == 2


def test_align_raises_when_no_markers_present():
    blank_photo = np.full((400, 300), 255, dtype=np.uint8)
    document = build_minimal_template_document(num_pages=1)

    with pytest.raises(AlignmentError):
        align_page_to_template(blank_photo, document, dpi=DPI)


def test_align_raises_when_too_few_markers_detected():
    document = build_minimal_template_document(num_pages=1)
    page = document.pages[0]
    template_image = render_template_page_image(document, page, DPI)

    # Blank out 2 of the 4 markers so only 2 remain — below the default
    # minimum of 3 needed to trust a homography fit.
    for marker in page.markers[:2]:
        corners = marker_corners_px(marker, document.page_size.height, DPI)
        template_image = blank_out_region(template_image, corners)

    with pytest.raises(AlignmentError):
        align_page_to_template(template_image, document, dpi=DPI)


def test_align_raises_when_page_not_in_document():
    full_document = build_minimal_template_document(num_pages=2)
    page_2 = full_document.pages[1]
    template_image = render_template_page_image(full_document, page_2, DPI)

    # A document that only knows about page 1 — page 2's markers won't
    # resolve to any page in it.
    page_1_only_document = build_minimal_template_document(num_pages=1)

    with pytest.raises(AlignmentError):
        align_page_to_template(template_image, page_1_only_document, dpi=DPI)
