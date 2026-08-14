from __future__ import annotations

from dataclasses import dataclass, field

# Spec §12's literal sample lines.
DEFAULT_SAMPLE_LINES: tuple[str, ...] = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "abcdefghijklmnopqrstuvwxyz",
    "0123456789",
    "The quick brown fox jumps over the lazy dog.",
)


@dataclass(frozen=True)
class PreviewConfig:
    image_width: int = 1000
    image_height: int = 420
    font_size: int = 44
    line_spacing: int = 70
    margin: int = 40
    sample_lines: tuple[str, ...] = field(default_factory=lambda: DEFAULT_SAMPLE_LINES)
