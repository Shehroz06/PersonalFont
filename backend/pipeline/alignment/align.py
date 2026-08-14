"""Stage 8 (spec §5/§6): align a photographed page to a specific template
page and warp it into the template's pixel coordinate space, so character
extraction (Phase 5) can crop glyphs using the template JSON's coordinates
directly.

Marker IDs encode `page_index * 4 + corner_index` (see layout.py), so the
page a photo belongs to is recovered from the detected marker IDs alone —
the caller does not need to know in advance which page was uploaded.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from app.template_gen.coordinates import marker_corners_px, page_size_px
from app.template_gen.layout import MARKER_CORNERS
from app.template_gen.schema import TemplateDocument, TemplatePage
from pipeline.alignment.confidence import compute_alignment_confidence
from pipeline.alignment.errors import AlignmentError
from pipeline.alignment.homography import estimate_homography
from pipeline.alignment.marker_detection import DetectedMarker, detect_markers

DEFAULT_MIN_MATCHED_MARKERS = 3
DEFAULT_MAX_REPROJECTION_ERROR_PX = 8.0
DEFAULT_MIN_CONFIDENCE = 0.6


@dataclass(frozen=True)
class AlignmentResult:
    page: TemplatePage
    aligned_image: np.ndarray
    homography: np.ndarray
    confidence: float
    matched_markers: int
    expected_markers: int
    mean_reprojection_error_px: float


def _resolve_page(detected: list[DetectedMarker], document: TemplateDocument) -> TemplatePage:
    if not detected:
        raise AlignmentError(
            f"No {document.template_id} alignment markers were detected in the uploaded image. "
            "Please upload a clearer photograph showing the full page with all four corner "
            "markers visible."
        )

    votes: dict[int, int] = {}
    for marker in detected:
        page_index = marker.marker_id // len(MARKER_CORNERS)
        votes[page_index] = votes.get(page_index, 0) + 1
    voted_page_index = max(votes, key=votes.get)
    page_number = voted_page_index + 1

    for page in document.pages:
        if page.page == page_number:
            return page

    raise AlignmentError(
        f"The detected markers correspond to page {page_number}, which is not part of "
        f"{document.template_id}. Please check you are uploading pages from the correct template."
    )


def align_page_to_template(
    image: np.ndarray,
    document: TemplateDocument,
    dpi: float,
    min_matched_markers: int = DEFAULT_MIN_MATCHED_MARKERS,
    max_reprojection_error_px: float = DEFAULT_MAX_REPROJECTION_ERROR_PX,
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> AlignmentResult:
    """Locate, identify, and rectify a photographed template page.

    Raises AlignmentError with an actionable message (spec §17) if the
    page's template/version can't be determined, or if it can but too few
    markers were found or the resulting fit is too poor to trust.
    """
    detected = detect_markers(image)
    page = _resolve_page(detected, document)

    expected_corners_px = {
        marker.marker_id: marker_corners_px(marker, document.page_size.height, dpi) for marker in page.markers
    }
    matched = [m for m in detected if m.marker_id in expected_corners_px]

    if len(matched) < min_matched_markers:
        raise AlignmentError(
            f"Page {page.page} could not be reliably aligned with {document.template_id}: only "
            f"{len(matched)} of {len(expected_corners_px)} alignment markers were found. "
            "Please upload a clearer image with all four corner markers visible."
        )

    homography, mean_error = estimate_homography(matched, expected_corners_px)
    confidence = compute_alignment_confidence(
        matched_markers=len(matched),
        expected_markers=len(expected_corners_px),
        mean_reprojection_error_px=mean_error,
        max_reprojection_error_px=max_reprojection_error_px,
    )

    if confidence < min_confidence:
        raise AlignmentError(
            f"Page {page.page} could not be reliably aligned with {document.template_id} "
            f"(confidence {confidence:.2f}, below the required {min_confidence:.2f}). "
            "Please upload a clearer, flatter photograph taken straight-on."
        )

    output_size = page_size_px(document.page_size.width, document.page_size.height, dpi)
    aligned_image = cv2.warpPerspective(image, homography, output_size)

    return AlignmentResult(
        page=page,
        aligned_image=aligned_image,
        homography=homography,
        confidence=confidence,
        matched_markers=len(matched),
        expected_markers=len(expected_corners_px),
        mean_reprojection_error_px=mean_error,
    )
