"""Turns raw alignment signals (how many markers matched, how well the
fitted homography reprojects them) into a single 0-1 confidence score,
used to decide whether to accept or reject a page (spec §6)."""

from __future__ import annotations


def compute_alignment_confidence(
    matched_markers: int,
    expected_markers: int,
    mean_reprojection_error_px: float,
    max_reprojection_error_px: float,
) -> float:
    """coverage: fraction of expected markers actually matched.
    accuracy: how close the fitted homography's reprojection is to
    perfect, linearly scaled to 0 at max_reprojection_error_px.

    Confidence is their product, so a page with all markers found but a
    poor-quality fit (e.g. a blurry photo) still scores low, and vice
    versa.
    """
    coverage = min(1.0, matched_markers / expected_markers) if expected_markers else 0.0
    accuracy = max(0.0, 1.0 - mean_reprojection_error_px / max_reprojection_error_px)
    return round(coverage * accuracy, 4)
