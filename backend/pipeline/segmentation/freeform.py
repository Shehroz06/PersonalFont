"""Segments individually-written characters from a plain page — no
template, no ArUco markers, no printed boxes — matched in row-major
reading order against a caller-supplied ordered list of expected
character ids.

Exists because requiring a full template reprint (with its markers) just
to rewrite a handful of characters flagged by review is real, unnecessary
friction for what should be a quick fix (spec §16's character-review
"identify which characters need rewriting" flow implies a fast rewrite
loop, not a full resubmission). A user can jot the flagged characters on
any blank sheet, in simple rows, and have them matched up automatically
instead. This is classical image processing — thresholding, connected
components, spatial clustering — not generative AI or ML, so it stays
within V1's deterministic-only constraint.

Deliberately conservative: if the number of detected ink blobs doesn't
exactly match the number of expected characters, this raises rather than
guessing at a best-effort alignment. Silently mis-assigning "the 5th blob
I found" to "the 5th character I expected" when those two counts
disagree would risk mislabeling a glyph with no way for validation to
catch it — worse than the segmentation failures elsewhere in this
pipeline raise for, since those are caught downstream by validation but
a wrong *label* here would not be.

A single handwritten character is frequently more than one connected
component — "i"'s dot and stem, ":"'s two dots, ";", ","'s tail catching
a stray pixel gap — so raw connected components can't be used as
characters directly (verified against a real plain-paper scan: 53 raw
components for 23 actual characters). Two merge steps run before
matching against ``expected_character_ids``:

1. Nearby raw components are unioned into one group when the gap between
   their bounding boxes is under ``merge_gap_ratio`` of the image width.
   Calibrated against that same real scan: sweeping the gap threshold
   from 25px to 70+px (1.0%-2.8% of the 2480px-wide page) all land on
   the same, correct 23-group result — a wide, stable plateau, and
   ``merge_gap_ratio`` sits comfortably inside it rather than at an edge.
2. Any merged group whose bounding box comes within ``border_margin_ratio``
   of the image edge is dropped as a scan artifact, not handwriting — real
   phone/scanning-app photos of a page reliably show color-fringing and
   compression noise right at the page edge (observed directly on the
   calibration scan: 4 extra components at kernel-merge time, all hugging
   the image border, none anywhere near the actual handwriting).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from app.template_gen.character_set import character_set_by_id
from pipeline.ink_geometry import DEFAULT_MIN_COMPONENT_AREA_RATIO, remove_small_components
from pipeline.preprocessing.grayscale import to_grayscale
from pipeline.preprocessing.noise_removal import remove_noise
from pipeline.preprocessing.thresholding import binarize_otsu
from pipeline.segmentation.schema import ExtractedGlyph, GlyphCropBox


class FreeformExtractionError(Exception):
    """Raised when the detected ink blobs on a plain page can't be
    confidently matched to the expected character list."""


# Not a real template page number — extract_ordered_glyphs has no
# template/page concept, but ExtractedGlyph.page exists for the
# template-based path and needs *some* value.
FREEFORM_PAGE_SENTINEL = 0


@dataclass(frozen=True)
class FreeformExtractionConfig:
    # Components smaller than this many pixels are dropped outright
    # before row/column clustering even runs — stray specks, not
    # candidate characters.
    min_component_area_px: int = 12

    # Raw components whose bounding boxes are closer than this fraction
    # of the image width are merged into a single character before
    # matching — see the module docstring for the real-scan calibration.
    # Expressed as a ratio (not a fixed pixel count) so it scales with
    # scan resolution/page size rather than assuming one specific DPI.
    merge_gap_ratio: float = 0.018

    # A merged group is dropped as a scan-edge artifact if its bounding
    # box comes within this fraction of the image width/height of the
    # border — see module docstring.
    border_margin_ratio: float = 0.01

    # A new row starts when the vertical gap between consecutive
    # components (by y-center, sorted) exceeds this multiple of the
    # median component height on the page — adapts to whatever scale the
    # page was written/scanned at, rather than a fixed pixel gap.
    row_gap_multiplier: float = 1.4

    padding_px: int = 10

    # Same within-glyph noise cleanup as the template-based path (see
    # pipeline.ink_geometry and pipeline.segmentation.extract) — same
    # calibration, same reasoning: scan/compression noise vs. a
    # legitimate second stroke.
    min_component_area_ratio: float = DEFAULT_MIN_COMPONENT_AREA_RATIO


def _binarize(image: np.ndarray) -> np.ndarray:
    gray = to_grayscale(image)
    denoised = remove_noise(gray)
    return binarize_otsu(denoised)


Box = tuple[int, int, int, int]  # x, y, w, h


def _edge_gap(a: Box, b: Box) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    dx = max(ax - (bx + bw), bx - (ax + aw), 0)
    dy = max(ay - (by + bh), by - (ay + ah), 0)
    return (dx**2 + dy**2) ** 0.5


def _merge_fragmented_components(boxes: list[Box], gap_threshold: float) -> list[Box]:
    """Unions raw components whose bounding boxes are within
    ``gap_threshold`` of each other — merges a character's separate
    strokes (dot+stem, multi-part punctuation) back into one box."""
    parent = list(range(len(boxes)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        pi, pj = find(i), find(j)
        if pi != pj:
            parent[pi] = pj

    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if _edge_gap(boxes[i], boxes[j]) < gap_threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(len(boxes)):
        groups.setdefault(find(i), []).append(i)

    merged: list[Box] = []
    for members in groups.values():
        x0 = min(boxes[i][0] for i in members)
        y0 = min(boxes[i][1] for i in members)
        x1 = max(boxes[i][0] + boxes[i][2] for i in members)
        y1 = max(boxes[i][1] + boxes[i][3] for i in members)
        merged.append((x0, y0, x1 - x0, y1 - y0))

    return merged


def _drop_border_artifacts(
    boxes: list[Box], image_width: int, image_height: int, margin_ratio: float
) -> list[Box]:
    """Drops merged groups whose bounding box touches near the image
    edge — real handwriting sits inside the page, not at the border of
    the photo; scan/compression artifacts reliably do the opposite."""
    margin_x = margin_ratio * image_width
    margin_y = margin_ratio * image_height
    kept = []
    for x, y, w, h in boxes:
        if x <= margin_x or y <= margin_y or x + w >= image_width - margin_x or y + h >= image_height - margin_y:
            continue
        kept.append((x, y, w, h))
    return kept


def _cluster_into_rows(
    boxes: list[tuple[int, int, int, int]],
    row_gap_multiplier: float,
) -> list[int]:
    """``boxes``: (x, y, w, h) per detected component. Returns indices
    into ``boxes`` in row-major reading order (top-to-bottom rows,
    left-to-right within each row)."""
    heights = [h for _, _, _, h in boxes]
    median_height = float(np.median(heights))
    row_gap_threshold = median_height * row_gap_multiplier

    def y_center(i: int) -> float:
        return boxes[i][1] + boxes[i][3] / 2

    order = sorted(range(len(boxes)), key=y_center)

    rows: list[list[int]] = [[order[0]]]
    prev_y_center = y_center(order[0])

    for idx in order[1:]:
        current_y_center = y_center(idx)
        if current_y_center - prev_y_center > row_gap_threshold:
            rows.append([])
        rows[-1].append(idx)
        prev_y_center = current_y_center

    for row in rows:
        row.sort(key=lambda i: boxes[i][0])  # left to right by x

    return [i for row in rows for i in row]


def extract_ordered_glyphs(
    image: np.ndarray,
    expected_character_ids: list[str],
    job_id: str,
    output_dir: Path,
    source_image: str,
    config: FreeformExtractionConfig | None = None,
) -> list[ExtractedGlyph]:
    """Detect ink blobs on a plain page, order them by reading position
    (row-major, top-to-bottom then left-to-right), and match them 1:1
    against ``expected_character_ids`` in the order given.

    Raises FreeformExtractionError if no ink is found, or if the
    detected-blob count doesn't exactly match ``len(expected_character_ids)``
    — see the module docstring for why this doesn't try to guess.
    """
    config = config or FreeformExtractionConfig()
    output_dir.mkdir(parents=True, exist_ok=True)

    binary = _binarize(image)
    image_height, image_width = binary.shape[:2]
    num_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(binary, connectivity=8)

    raw_boxes: list[tuple[int, int, int, int]] = []
    for label in range(1, num_labels):  # label 0 is background
        x, y, w, h, area = stats[label]
        if area < config.min_component_area_px:
            continue
        raw_boxes.append((x, y, w, h))

    if not raw_boxes:
        raise FreeformExtractionError(
            "No handwriting was detected on this page. Please make sure the page is well lit, "
            "in focus, and the ink is dark enough to see clearly."
        )

    gap_threshold = config.merge_gap_ratio * image_width
    merged_boxes = _merge_fragmented_components(raw_boxes, gap_threshold)
    boxes = _drop_border_artifacts(merged_boxes, image_width, image_height, config.border_margin_ratio)

    if not boxes:
        raise FreeformExtractionError(
            "No handwriting was detected on this page. Please make sure the page is well lit, "
            "in focus, and the ink is dark enough to see clearly."
        )

    ordered_indices = _cluster_into_rows(boxes, config.row_gap_multiplier)

    if len(ordered_indices) != len(expected_character_ids):
        raise FreeformExtractionError(
            f"Found {len(ordered_indices)} handwritten character(s) on this page, but expected "
            f"{len(expected_character_ids)}. Please check that each character is written clearly "
            "apart from its neighbors (no touching strokes), that nothing extra was written, and "
            "that none of the expected characters were skipped."
        )

    character_lookup = character_set_by_id()
    results: list[ExtractedGlyph] = []

    for position, character_id in zip(ordered_indices, expected_character_ids):
        spec = character_lookup.get(character_id)
        if spec is None:
            raise FreeformExtractionError(
                f"Unknown character id {character_id!r}: not part of the configured character set."
            )

        x, y, w, h = boxes[position]
        x0 = max(0, x - config.padding_px)
        y0 = max(0, y - config.padding_px)
        x1 = min(image_width, x + w + config.padding_px)
        y1 = min(image_height, y + h + config.padding_px)

        crop = binary[y0:y1, x0:x1]
        crop = remove_small_components(crop, config.min_component_area_ratio)

        image_path = output_dir / f"{character_id}.png"
        cv2.imwrite(str(image_path), crop)

        results.append(
            ExtractedGlyph(
                job_id=job_id,
                page=FREEFORM_PAGE_SENTINEL,
                character=spec.character,
                character_id=character_id,
                source_image=source_image,
                crop_box=GlyphCropBox(x=x0, y=y0, width=x1 - x0, height=y1 - y0),
                extraction_confidence=1.0,
                image_path=str(image_path),
            )
        )

    return results
