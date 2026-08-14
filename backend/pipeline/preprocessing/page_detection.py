"""Stage 1: find the sheet of paper's boundary within a photograph.

This looks for the largest 4-sided contour with a plausible area — it does
not know anything about the template's ArUco markers or character grid.
Matching the photo to a *specific* template (and rejecting mismatched or
low-confidence alignments per spec §6) is the alignment stage's job
(Phase 4), which runs after this.
"""

from __future__ import annotations

import cv2
import numpy as np

from pipeline.preprocessing.errors import PageDetectionError
from pipeline.preprocessing.geometry import order_points

# A detected quadrilateral smaller than this fraction of the total image
# area is assumed to be noise, not the page.
MIN_PAGE_AREA_RATIO = 0.2


def detect_page_contour(
    image: np.ndarray,
    min_area_ratio: float = MIN_PAGE_AREA_RATIO,
) -> np.ndarray:
    """Return the 4 corners of the page, ordered (tl, tr, br, bl).

    Raises PageDetectionError if no sufficiently large quadrilateral is
    found — e.g. the photo doesn't clearly show the whole page, or the
    background doesn't contrast with the paper.
    """
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 50, 150)
    edges = cv2.dilate(edges, np.ones((5, 5), np.uint8), iterations=1)

    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise PageDetectionError(
            "No page boundary could be detected in the uploaded image. "
            "Please retake the photo with the full page visible against a "
            "contrasting background and even lighting."
        )

    image_area = image.shape[0] * image.shape[1]
    min_area = image_area * min_area_ratio

    for contour in sorted(contours, key=cv2.contourArea, reverse=True):
        area = cv2.contourArea(contour)
        if area < min_area:
            break

        perimeter = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * perimeter, True)

        if len(approx) == 4 and cv2.isContourConvex(approx):
            return order_points(approx.astype(np.float32))

    raise PageDetectionError(
        "The page could not be reliably located in the uploaded image "
        "(no clear four-cornered page boundary found). Please retake the "
        "photo with the full page visible, flat, and well lit."
    )
