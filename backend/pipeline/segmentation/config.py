from __future__ import annotations

from dataclasses import dataclass

from pipeline.ink_geometry import DEFAULT_MIN_COMPONENT_AREA_RATIO


@dataclass(frozen=True)
class SegmentationConfig:
    # Handwriting routinely overflows its guide box slightly (an ascender,
    # a wide flourish); a small padding avoids clipping it. Whether the
    # resulting crop still looks wrong (e.g. it now touches the crop
    # boundary) is validation's job (Phase 6), not this stage's.
    padding_px: int = 6

    # Connected components smaller than this fraction of the crop's
    # largest component are dropped right after cropping (see
    # pipeline.ink_geometry.remove_small_components) — cleans up scan/
    # compression noise speckle (and, on templates printed before the
    # background guide glyph was removed, its ghosting) before it ever
    # reaches validation or normalization, without discarding legitimate
    # secondary strokes like the dot on an "i"/"j".
    min_component_area_ratio: float = DEFAULT_MIN_COMPONENT_AREA_RATIO
