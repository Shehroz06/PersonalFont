from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizationConfig:
    # The normalized output canvas — a fixed-size bitmap "em square" every
    # glyph is placed into, so all glyphs share one coordinate space going
    # into vectorization (Phase 8) and font generation (Phase 9).
    canvas_width: int = 500
    canvas_height: int = 500

    # Where the shared baseline sits, as a fraction of canvas_height down
    # from the top.
    baseline_ratio: float = 0.75

    # Main-body height targets (from the baseline upward), as a fraction
    # of canvas_height — see app.template_gen.character_set.is_tall_glyph.
    tall_height_ratio: float = 0.60
    short_height_ratio: float = 0.40

    # Extra height below the baseline reserved for descenders, as a
    # fraction of canvas_height.
    descender_ratio: float = 0.18

    # Minimum side margin (each side), as a fraction of canvas_width —
    # keeps a wide glyph's scale from reaching all the way to the edges.
    horizontal_margin_ratio: float = 0.10
