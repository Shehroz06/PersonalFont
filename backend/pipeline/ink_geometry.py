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
# treated as noise speck rather than a deliberate second stroke.
#
# Calibrated against a real photographed/scanned 76-character page, not
# guessed — and re-checked after an initial value (0.15) turned out to be
# far too conservative: sweeping the threshold against every character's
# *actual, expected* component count (including the 1-2 range for
# i/j/:/;/") showed a hard ceiling at 0.4385, the real ratio of a
# genuine "j" dot to its stem on that page. Above that ceiling, real
# secondary strokes start being discarded — confirmed directly on
# ":"/";" too, which stay safe only up to ~0.50-0.57. Below the ceiling,
# 0.40 (with a deliberate safety margin under 0.4385, not the ceiling
# itself) cleans up markedly more real noise than 0.15 did (67 of 76
# characters landed at their correct component count on that test page,
# vs 43 of 76 at 0.15) while still never touching any of the five
# multi-stroke characters' legitimate second stroke. Some noise on that
# same page exceeded even that ceiling (e.g. one single-stroke
# character's residual speckle measured ~50-60% of its real stroke) —
# no single global ratio can remove that without also risking a real
# "j" dot, so it's intentionally left for validation to flag rather than
# risk a false "valid" via an overly aggressive cutoff.
DEFAULT_MIN_COMPONENT_AREA_RATIO = 0.40


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
