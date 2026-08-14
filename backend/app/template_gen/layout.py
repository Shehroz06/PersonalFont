"""Computes where every character box and alignment marker sits on the page.

This module only produces *geometry* (a list of pages, each with element
boxes and marker boxes, in PDF point units with origin at bottom-left). It
knows nothing about PDF rendering or JSON serialization — those live in
pdf_renderer.py and schema.py respectively, so the layout math can be unit
tested without touching reportlab or the filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
from reportlab.lib.pagesizes import A4

from app.template_gen.character_set import CharacterSpec, get_character_set

# ArUco marker corner names, in a fixed order used for id assignment and
# rendering. Each page reuses the same 4 corner slots; the page index is
# folded into the marker id so a detector can recover which page (and which
# corner) it is looking at from the marker id alone.
MARKER_CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right")

# Shared across template generation (pdf_renderer) and alignment (Phase 4
# marker detection) — both must agree on the same dictionary or generated
# markers won't decode.
ARUCO_DICTIONARY = cv2.aruco.DICT_4X4_50

POINTS_PER_INCH = 72.0


@dataclass(frozen=True)
class LayoutConfig:
    page_width: float = A4[0]
    page_height: float = A4[1]

    margin: float = 42.0  # outer margin reserved for markers, in points
    marker_size: float = 28.0

    header_height: float = 54.0  # space at top for title / page number

    cell_width: float = 52.0
    cell_height: float = 62.0  # taller than wide: leaves room for a label
    cell_gap: float = 10.0

    @property
    def content_left(self) -> float:
        return self.margin + self.marker_size + self.cell_gap

    @property
    def content_right(self) -> float:
        return self.page_width - self.margin - self.marker_size - self.cell_gap

    @property
    def content_top(self) -> float:
        return self.page_height - self.margin - self.marker_size - self.header_height

    @property
    def content_bottom(self) -> float:
        return self.margin + self.marker_size + self.cell_gap

    @property
    def columns(self) -> int:
        available = self.content_right - self.content_left
        return max(1, int((available + self.cell_gap) // (self.cell_width + self.cell_gap)))

    @property
    def rows(self) -> int:
        available = self.content_top - self.content_bottom
        return max(1, int((available + self.cell_gap) // (self.cell_height + self.cell_gap)))

    @property
    def cells_per_page(self) -> int:
        return self.columns * self.rows


@dataclass(frozen=True)
class MarkerBox:
    marker_id: int
    corner: str  # one of MARKER_CORNERS
    x: float
    y: float
    size: float


@dataclass(frozen=True)
class ElementBox:
    character: str
    character_id: str
    category: str
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class PageLayout:
    page: int
    elements: list[ElementBox] = field(default_factory=list)
    markers: list[MarkerBox] = field(default_factory=list)


def _markers_for_page(page_index: int, config: LayoutConfig) -> list[MarkerBox]:
    m = config.marker_size
    positions = {
        "top_left": (config.margin, config.page_height - config.margin - m),
        "top_right": (config.page_width - config.margin - m, config.page_height - config.margin - m),
        "bottom_left": (config.margin, config.margin),
        "bottom_right": (config.page_width - config.margin - m, config.margin),
    }
    markers = []
    for corner_index, corner in enumerate(MARKER_CORNERS):
        x, y = positions[corner]
        marker_id = page_index * len(MARKER_CORNERS) + corner_index
        markers.append(MarkerBox(marker_id=marker_id, corner=corner, x=x, y=y, size=m))
    return markers


def compute_layout(
    characters: tuple[CharacterSpec, ...] | None = None,
    config: LayoutConfig | None = None,
) -> list[PageLayout]:
    """Pack the character set into pages of a fixed grid.

    Characters are placed left-to-right, top-to-bottom, filling as many
    boxes as fit per page (config.cells_per_page) before starting a new
    page. Grid geometry (rows/columns/box size) is entirely driven by
    LayoutConfig, so nothing here is hardcoded per character.
    """
    characters = characters if characters is not None else get_character_set()
    config = config or LayoutConfig()

    pages: list[PageLayout] = []
    per_page = config.cells_per_page

    for page_start in range(0, len(characters), per_page):
        page_chars = characters[page_start : page_start + per_page]
        page_index = page_start // per_page

        elements: list[ElementBox] = []
        for i, spec in enumerate(page_chars):
            row = i // config.columns
            col = i % config.columns

            x = config.content_left + col * (config.cell_width + config.cell_gap)
            top_y = config.content_top - row * (config.cell_height + config.cell_gap)
            y = top_y - config.cell_height

            elements.append(
                ElementBox(
                    character=spec.character,
                    character_id=spec.character_id,
                    category=spec.category,
                    x=round(x, 2),
                    y=round(y, 2),
                    width=config.cell_width,
                    height=config.cell_height,
                )
            )

        pages.append(
            PageLayout(
                page=page_index + 1,
                elements=elements,
                markers=_markers_for_page(page_index, config),
            )
        )

    return pages
