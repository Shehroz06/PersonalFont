"""Preprocessing configuration, including the rectified-page pixel size.

The target size is derived from the template's page dimensions (points,
defined once in app.template_gen.layout.LayoutConfig) and a working DPI,
rather than a second hardcoded page size — the rectified image must line
up with the template JSON's coordinate space for alignment (Phase 4) to
work.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.template_gen.coordinates import page_size_px
from app.template_gen.layout import LayoutConfig

DEFAULT_WORKING_DPI = 200


@dataclass(frozen=True)
class PreprocessingConfig:
    working_dpi: int = DEFAULT_WORKING_DPI
    page_width_pt: float = LayoutConfig().page_width
    page_height_pt: float = LayoutConfig().page_height
    min_page_area_ratio: float = 0.2
    threshold_method: str = "otsu"  # "otsu" | "adaptive"

    @property
    def output_size_px(self) -> tuple[int, int]:
        return page_size_px(self.page_width_pt, self.page_height_pt, self.working_dpi)
