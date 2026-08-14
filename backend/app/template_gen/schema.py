"""Pydantic models for the template JSON contract described in the project
spec (section 4). This is the data-driven description of a template: where
every character box and alignment marker sits. The segmentation/alignment
pipeline (Phase 3+) reads this file — it must never hardcode coordinates.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.template_gen.layout import MarkerBox, PageLayout


class PageSize(BaseModel):
    width: float
    height: float
    unit: str = "pt"


class TemplateMarker(BaseModel):
    marker_id: int
    corner: str
    x: float
    y: float
    size: float
    dictionary: str = "DICT_4X4_50"


class TemplateElement(BaseModel):
    character: str
    id: str
    category: str
    unicode: str
    x: float
    y: float
    width: float
    height: float


class TemplatePage(BaseModel):
    page: int
    elements: list[TemplateElement]
    markers: list[TemplateMarker]


class TemplateDocument(BaseModel):
    template_version: str
    template_id: str
    page_size: PageSize
    character_count: int
    pages: list[TemplatePage]


def _marker_to_model(marker: MarkerBox) -> TemplateMarker:
    return TemplateMarker(
        marker_id=marker.marker_id,
        corner=marker.corner,
        x=marker.x,
        y=marker.y,
        size=marker.size,
    )


def build_template_document(
    template_id: str,
    template_version: str,
    page_layouts: list[PageLayout],
    page_width: float,
    page_height: float,
) -> TemplateDocument:
    pages: list[TemplatePage] = []
    total_elements = 0

    for layout in page_layouts:
        elements = [
            TemplateElement(
                character=el.character,
                id=el.character_id,
                category=el.category,
                unicode=f"U+{ord(el.character):04X}",
                x=el.x,
                y=el.y,
                width=el.width,
                height=el.height,
            )
            for el in layout.elements
        ]
        total_elements += len(elements)

        pages.append(
            TemplatePage(
                page=layout.page,
                elements=elements,
                markers=[_marker_to_model(m) for m in layout.markers],
            )
        )

    return TemplateDocument(
        template_version=template_version,
        template_id=template_id,
        page_size=PageSize(width=page_width, height=page_height),
        character_count=total_elements,
        pages=pages,
    )
