from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SegmentationConfig:
    # Handwriting routinely overflows its guide box slightly (an ascender,
    # a wide flourish); a small padding avoids clipping it. Whether the
    # resulting crop still looks wrong (e.g. it now touches the crop
    # boundary) is validation's job (Phase 6), not this stage's.
    padding_px: int = 6
