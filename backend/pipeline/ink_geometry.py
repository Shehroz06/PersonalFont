"""Generic geometry helpers for binary (ink=255/background=0) glyph
images — shared by validation (Phase 6) and normalization (Phase 7) rather
than each re-deriving "how much ink, and where" from scratch.

See pipeline.preprocessing.thresholding for the ink=255/background=0
convention every caller of this module assumes.
"""

from __future__ import annotations

import cv2
import numpy as np


def ink_pixel_count(image: np.ndarray) -> int:
    return int(np.count_nonzero(image))


def ink_bounding_box(image: np.ndarray) -> tuple[int, int, int, int] | None:
    """Tight (x0, y0, x1, y1) bounding box of ink pixels, or None if empty."""
    coords = cv2.findNonZero(image)
    if coords is None:
        return None
    x, y, w, h = cv2.boundingRect(coords)
    return x, y, x + w, y + h


# Below this fraction of the largest component's area, a component is
# treated as noise speck rather than a deliberate second stroke. Chosen
# from real data, not guessed: on an actual photographed/scanned glyph
# crop, a legitimate secondary stroke (e.g. the dot on a "j") measured at
# ~41% of the main stroke's area, comfortably above this cutoff, while
# scan-artifact speckle (JPEG/compression noise, a partially-surviving
# background element) measured well under 10%.
DEFAULT_MIN_COMPONENT_AREA_RATIO = 0.15


def remove_small_components(
    image: np.ndarray,
    min_area_ratio: float = DEFAULT_MIN_COMPONENT_AREA_RATIO,
) -> np.ndarray:
    """Drop connected ink components smaller than ``min_area_ratio`` of
    the largest component's area — cleans up small scan/compression noise
    speckle without discarding a legitimate second stroke (the dot on an
    "i"/"j", either dot of a ":", ...), which is reliably much larger
    relative to its companion stroke than noise speckle is.

    Returns ``image`` unchanged if it has 0 or 1 components (nothing to
    filter against).
    """
    num_labels, labels, stats, _centroids = cv2.connectedComponentsWithStats(image, connectivity=8)
    if num_labels <= 2:  # background + at most one component
        return image

    areas = stats[1:, cv2.CC_STAT_AREA]  # exclude background label 0
    max_area = areas.max()
    if max_area == 0:
        return image

    keep_labels = {label + 1 for label, area in enumerate(areas) if area >= max_area * min_area_ratio}

    cleaned = np.zeros_like(image)
    cleaned[np.isin(labels, list(keep_labels))] = 255
    return cleaned
