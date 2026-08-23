"""Renders a PageLayout list to a printable PDF.

Each character box is drawn as an empty rectangle — outlined in a light
grey that disappears under thresholding (see _BOX_STROKE_COLOR) — plus an
ID caption below it so the writer knows what to write. There is
deliberately no background guide glyph traced inside the box itself; see
the note below _BOX_STROKE_COLOR for why. ArUco markers are drawn at the
four corners of every page so the alignment stage (Phase 4) can robustly
recover the page's rotation, perspective and scale from a phone
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
# thresholding (pipeline.preprocessing.thresholding) the same way a light
# grey guide glyph would — verified empirically: a dark border survives
# thresholding as its own connected component, which makes an empty box
# validate as if it were a real single-stroke glyph, and makes a
# genuinely well-written character get rejected as "too many strokes"
# once the border and the real ink are both picked up as ink.
#
# An earlier version of this template also drew a large light-grey guide
# letter inside the box for the writer to trace over. That was removed
# entirely, not just lightened — verified against a real phone scan
# (Adobe Scan, iOS): scanning apps apply their own contrast/sharpening
# enhancement before we ever see the image, which can re-darken a
# carefully chosen light grey back into something Otsu picks up as ink.
# On that real scan, the large guide letter survived as visible ghosting
# and caused 53 of 56 characters to fail validation as "too many
# strokes," while the much thinner 1px box border (same nominal color)
# did not reappear — the fix is to remove the large-area guide glyph
# rather than trust a specific grey value to survive arbitrary
# third-party image processing pipelines we don't control.
_BOX_STROKE_COLOR = _GUIDE_COLOR

_CAPTION_FONT_SIZE = 6


def _caption_for(character_id: str) -> str:
    """The printed label under a box — character_id with any category
    prefix stripped, since the full id (e.g. "punctuation_bracket_close")
    is wider than the box itself at a legible size. Verified against
    every entry in the real character set: the longest surviving label
    ("bracket_close", ~37pt) comfortably fits a 52pt-wide box, where
    several full character_ids (up to ~71pt) did not."""
    prefix, _sep, rest = character_id.partition("_")
    return rest if prefix == "punctuation" and rest else character_id


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

    # Character boxes — deliberately no background guide glyph traced
    # inside; see the note above _BOX_STROKE_COLOR. Since the guide glyph
    # is gone, this caption is now the *only* thing telling the writer
    # which character goes in which box, so it has to actually fit.
    c.setLineWidth(1)
    for element in layout.elements:
        c.setStrokeColor(_BOX_STROKE_COLOR)
        c.rect(element.x, element.y, element.width, element.height, stroke=1, fill=0)

        c.setFont("Helvetica", _CAPTION_FONT_SIZE)
        c.setFillColor(_LABEL_COLOR)
        c.drawCentredString(
            element.x + element.width / 2,
            element.y - 7,
            _caption_for(element.character_id),
        )
