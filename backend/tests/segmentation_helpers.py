"""Synthetic template/photo builders shared by the segmentation tests.

Builds on tests/alignment_helpers.py's minimal template, adding a couple
of character elements and ink content so extraction has something real to
crop. Not a test module itself (no test_ prefix) — pytest won't collect it.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.template_gen.coordinates import element_box_px
from app.template_gen.schema import PageSize, TemplateDocument, TemplateElement, TemplatePage
from tests.alignment_helpers import (
    MARGIN_PT,
    MARKER_SIZE_PT,
    PAGE_HEIGHT_PT,
    PAGE_WIDTH_PT,
    markers_for_page,
    render_template_page_image,
)

BOX_SIZE_PT = 60.0


def _elements_for_page(page_index: int) -> list[TemplateElement]:
    x0 = MARGIN_PT + MARKER_SIZE_PT + 20
    y = PAGE_HEIGHT_PT / 2
    return [
        TemplateElement(
            character="A",
            id=f"page{page_index}_uppercase_A",
            category="uppercase",
            unicode="U+0041",
            x=x0,
            y=y,
            width=BOX_SIZE_PT,
            height=BOX_SIZE_PT,
        ),
        TemplateElement(
            character="B",
            id=f"page{page_index}_uppercase_B",
            category="uppercase",
            unicode="U+0042",
            x=x0 + BOX_SIZE_PT + 20,
            y=y,
            width=BOX_SIZE_PT,
            height=BOX_SIZE_PT,
        ),
    ]


def build_template_document_with_elements(num_pages: int, template_id: str = "template_test_elems") -> TemplateDocument:
    pages = [
        TemplatePage(page=i + 1, elements=_elements_for_page(i), markers=markers_for_page(i))
        for i in range(num_pages)
    ]
    return TemplateDocument(
        template_version="1.0",
        template_id=template_id,
        page_size=PageSize(width=PAGE_WIDTH_PT, height=PAGE_HEIGHT_PT),
        character_count=sum(len(p.elements) for p in pages),
        pages=pages,
    )


def render_template_page_with_ink(document: TemplateDocument, page: TemplatePage, dpi: float) -> np.ndarray:
    """Markers (from alignment_helpers) plus a dark square drawn inside
    each element's box, standing in for handwritten ink."""
    canvas = render_template_page_image(document, page, dpi)

    for element in page.elements:
        x, y, w, h = element_box_px(element, document.page_size.height, dpi)
        x0, y0 = int(round(x)), int(round(y))
        x1, y1 = int(round(x + w)), int(round(y + h))
        cv2.rectangle(canvas, (x0 + 8, y0 + 8), (x1 - 8, y1 - 8), 0, thickness=4)

    return canvas
