"""Renders a PageLayout list to a printable PDF.

Each character box is drawn as an empty rectangle — outlined in a light
grey that disappears under thresholding, same as the guide glyph inside it
(see _BOX_STROKE_COLOR) — with a small guide glyph so the writer knows
what to write, plus an ID caption for debugging. ArUco markers are drawn
at the four corners of every page so the alignment stage (Phase 4) can
robustly recover the page's rotation, perspective and scale from a phone
photograph.
"""

from __future__ import annotations

import io

import cv2
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

from app.template_gen.layout import ARUCO_DICTIONARY, LayoutConfig, PageLayout

_GUIDE_COLOR = HexColor("#c9c9c9")
_HEADER_COLOR = HexColor("#333333")
_LABEL_COLOR = HexColor("#888888")

# The box outline must be light enough to disappear under Otsu
# thresholding (pipeline.preprocessing.thresholding) the same way the
# guide glyph does — verified empirically: a dark border survives
# thresholding as its own connected component, which makes an empty box
# validate as if it were a real single-stroke glyph, and makes a
# genuinely well-written character get rejected as "too many strokes"
# once the border and the real ink are both picked up as ink. Matching
# _GUIDE_COLOR exactly reuses a value already confirmed to vanish.
_BOX_STROKE_COLOR = _GUIDE_COLOR


def _render_marker_image(marker_id: int, pixels: int = 300) -> ImageReader:
    aruco_dict = cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY)
    marker_img = cv2.aruco.generateImageMarker(aruco_dict, marker_id, pixels)
    ok, encoded = cv2.imencode(".png", marker_img)
    if not ok:
        raise RuntimeError(f"Failed to encode ArUco marker {marker_id}")
    return ImageReader(io.BytesIO(encoded.tobytes()))


def render_template_pdf(
    page_layouts: list[PageLayout],
    output_path: str,
    config: LayoutConfig,
    template_id: str,
) -> None:
    c = canvas.Canvas(output_path, pagesize=(config.page_width, config.page_height))

    for layout in page_layouts:
        _render_page(c, layout, config, template_id)
        c.showPage()

    c.save()


def _render_page(
    c: canvas.Canvas,
    layout: PageLayout,
    config: LayoutConfig,
    template_id: str,
) -> None:
    # Header (indented past the top-left marker so the two never overlap)
    header_x = config.margin + config.marker_size + 12
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(_HEADER_COLOR)
    c.drawString(header_x, config.page_height - config.margin - 20, "PersonalFont Handwriting Template")

    c.setFont("Helvetica", 9)
    c.setFillColor(_LABEL_COLOR)
    c.drawString(
        header_x,
        config.page_height - config.margin - 34,
        f"{template_id}  |  page {layout.page}  |  write one character per box, staying inside the lines",
    )

    # Alignment markers
    for marker in layout.markers:
        marker_image = _render_marker_image(marker.marker_id)
        c.drawImage(
            marker_image,
            marker.x,
            marker.y,
            width=marker.size,
            height=marker.size,
            mask="auto",
        )

    # Character boxes
    c.setLineWidth(1)
    for element in layout.elements:
        c.setStrokeColor(_BOX_STROKE_COLOR)
        c.rect(element.x, element.y, element.width, element.height, stroke=1, fill=0)

        c.setFont("Helvetica", element.height * 0.55)
        c.setFillColor(_GUIDE_COLOR)
        c.drawCentredString(
            element.x + element.width / 2,
            element.y + element.height * 0.22,
            element.character,
        )

        c.setFont("Helvetica", 6)
        c.setFillColor(_LABEL_COLOR)
        c.drawCentredString(
            element.x + element.width / 2,
            element.y - 7,
            element.character_id,
        )
