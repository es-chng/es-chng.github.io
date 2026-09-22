#!/usr/bin/env python3
"""
Builds a PDF for one article, using the SAME frame-then-schema structure as the
webpage: a fixed base frame (title/authors/date, then DOI/pages/licence footer),
with the schema's fields walked in between, using the schema's own shape/style
instructions. No field names are hardcoded past the ten base fields.

Usage: python scripts/render_pdf.py _articles/FILE.md out.pdf
"""
import os
import pathlib
import re
import sys

import yaml
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
FM_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.S)

# Directories searched (in order) for the DejaVu TrueType faces. The renderer
# never assumes a font is present: if a face is missing it falls back to
# ReportLab's built-in standard fonts (see fonts()).
_FONT_DIRS = [
    "/usr/share/fonts/truetype/dejavu/",
    "/usr/share/fonts/truetype/",
    "/usr/share/fonts/",
    os.path.expanduser("~/.fonts"),
    os.path.expanduser("~/.local/share/fonts"),
]


def _find_font(filenames):
    """Return the path of the first of `filenames` found under any searched
    font directory (searched recursively), else None."""
    for base in _FONT_DIRS:
        if not os.path.isdir(base):
            continue
        for name in filenames:
            p = os.path.join(base, name)
            if os.path.isfile(p):
                return p
        for root, _dirs, files in os.walk(base):
            for name in filenames:
                if name in files:
                    return os.path.join(root, name)
    return None


def fonts():
    """Register and return the (body, bold, italic, sans) font names used
    throughout the document.

    Prefers the DejaVu family, which gives the intended academic-serif look
    and matches the webpage. If a DejaVu face is missing it falls back to
    ReportLab's built-in standard fonts -- Times-Roman / Times-Bold /
    Times-Italic (a serif, consistent with the DejaVu serif intent) and
    Helvetica -- which need no files and are always available. The known gap
    this closes: `DejaVuSerif-Italic.ttf` is shipped by `fonts-dejavu-extra`
    but NOT by `fonts-dejavu-core`, so a clean install that only has the core
    package used to crash the PDF step with TTFError. With this fallback the
    PDF always renders; at worst the typeface differs from the intended DejaVu
    serif, never a hard crash.
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    def _reg(alias, candidates, fallback):
        path = _find_font(candidates)
        if path:
            pdfmetrics.registerFont(TTFont(alias, path))
            return alias
        return fallback

    body = _reg("Body", ["DejaVuSerif.ttf"], "Times-Roman")
    bold = _reg("Body-Bold", ["DejaVuSerif-Bold.ttf"], "Times-Bold")
    italic = _reg(
        "Body-Italic",
        ["DejaVuSerif-Italic.ttf", "DejaVuSerif-Oblique.ttf", "DejaVuSans-Oblique.ttf"],
        "Times-Italic",
    )
    sans = _reg("Sans", ["DejaVuSans.ttf"], "Helvetica")

    # If the regular serif face itself is missing, normalise the whole serif
    # family to the built-in Times set so body/bold/italic stay consistent
    # rather than mixing (e.g.) a Times regular with a DejaVu bold.
    if body == "Times-Roman":
        bold, italic = "Times-Bold", "Times-Italic"
    return body, bold, italic, sans


def load_article(path):
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(FM_RE.match(text).group(1))


def load_schema(name):
    return yaml.safe_load((ROOT / "_data" / f"{name}.yml").read_text())


NARROW_COLUMNS = {"type"}
TABLE_AVAILABLE_WIDTH = 16.6 * cm  # A4 width minus the document's left/right margins


def compute_col_widths(cols, available=TABLE_AVAILABLE_WIDTH, narrow=NARROW_COLUMNS, narrow_w=2.3 * cm):
    """
    Column widths for a table field, computed from however many columns the schema
    declares -- never hardcoded for a fixed count. A schema can declare any number
    of table columns; a short one (like "type") stays narrow, and the rest share
    the remaining width evenly. Fixed widths sized for exactly two columns
    previously caused a third column to silently overflow the page edge instead
    of wrapping -- see tests in scripts/selftest.py.
    """
    n_narrow = sum(1 for c in cols if c in narrow)
    n_wide = len(cols) - n_narrow
    wide_w = (available - n_narrow * narrow_w) / max(n_wide, 1)
    return [narrow_w if c in narrow else wide_w for c in cols]


def build(article_path, out_path, doi_override=None):
    """
    Build one article PDF.
    doi_override: if set, used in the footer instead of article['doi'].
                  Used by the Zenodo deposit flow so the final PDF embeds
                  the real reserved DOI before upload.
    """
    article = load_article(pathlib.Path(article_path))
    body, bold, italic, sans = fonts()
    display_doi = doi_override if doi_override else article.get("doi")
    # Academic register, matching the webpage: one serif family throughout (no
    # separate sans-serif for labels), a near-monochrome palette, small-caps-style
    # section labels done via a slightly letter-spaced bold serif rather than a
    # different typeface, and no colour except a single muted brown for the DOI link.
    INK, MUTED, ACCENT = "#1a1a1a", "#55534f", "#5c3d2e"
    st = {
        "badge": ParagraphStyle("badge", fontName=body, fontSize=9.5, textColor=MUTED, spaceAfter=12),
        "title": ParagraphStyle("title", fontName=bold, fontSize=16.5, leading=21, spaceAfter=8, textColor=INK),
        "authors": ParagraphStyle("authors", fontName=italic, fontSize=10.5, textColor=INK),
        "date": ParagraphStyle("date", fontName=body, fontSize=9.5, textColor=MUTED, spaceAfter=14),
        "label": ParagraphStyle("label", fontName=bold, fontSize=10.5, spaceBefore=13, spaceAfter=4,
                                textColor=INK, leading=13),
        "text": ParagraphStyle("text", fontName=body, fontSize=10.5, leading=15, alignment=TA_JUSTIFY, textColor=INK),
        "text_italic": ParagraphStyle("text_italic", fontName=italic, fontSize=10.5, leading=15,
                                      alignment=TA_JUSTIFY, textColor=INK, leftIndent=10),
        "badge_value": ParagraphStyle("badge_value", fontName=italic, fontSize=10, textColor=MUTED),
        "bullet": ParagraphStyle("bullet", fontName=body, fontSize=10.5, leading=15, leftIndent=12, bulletIndent=0, textColor=INK),
        "footer": ParagraphStyle("footer", fontName=body, fontSize=9, textColor=MUTED, spaceBefore=10),
        "error": ParagraphStyle("error", fontName=italic, fontSize=9.5, textColor=MUTED),
    }
    story = []

    # ---- STEP 9: fixed base frame, identical structure to the webpage's base frame ----
    story.append(Paragraph(
        f"VOLUME {article['volume']}, ISSUE {article['issue']} · ARTICLE {article['order']}", st["badge"]))
    story.append(Paragraph(escape(article["title"]), st["title"]))
    names = ", ".join(f"{a['given']} {a['family']}" for a in article["authors"])
    story.append(Paragraph(escape(names), st["authors"]))
    story.append(Paragraph(f"Published {article['published_date']}", st["date"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color="#c9c5bc", spaceAfter=6))

    # ---- schema-driven middle: walk the schema exactly as schema-slot.html does ----
    schema_name = article.get("schema")
    if schema_name:
        schema = load_schema(schema_name)
        for field in schema["fields"]:
            if field.get("visibility") != "public":
                continue
            key = field["key"]
            value = article.get(key)
            empty = value is None or value == "" or value == []
            if empty:
                if not field.get("optional"):
                    story.append(Paragraph(f"[Missing required field: {escape(field['label'])}]", st["error"]))
                continue
            style_name = field.get("style", "plain")
            is_opinion = style_name == "opinion"
            text_style = st["text_italic"] if is_opinion else st["text"]

            if style_name != "badge":
                story.append(Paragraph(escape(field["label"]), st["label"]))

            shape = field["shape"]
            if shape == "text":
                if style_name == "badge":
                    story.append(Paragraph(f"{escape(field['label'])} &nbsp;&nbsp; "
                                           f"<i>{escape(str(value))}</i>", st["badge"]))
                elif style_name == "boxed":
                    # a thin rule above and below, not a filled colour box
                    story.append(HRFlowable(width="100%", thickness=0.5, color="#c9c5bc", spaceAfter=4))
                    story.append(Paragraph(escape(str(value)), text_style))
                    story.append(HRFlowable(width="100%", thickness=0.5, color="#c9c5bc", spaceBefore=4))
                else:
                    story.append(Paragraph(escape(str(value)), text_style))
            elif shape == "list" and isinstance(value, list):
                for item in value:
                    story.append(Paragraph(f"&bull; {escape(str(item))}", st["bullet"]))
            elif shape == "table":
                ok = isinstance(value, list) and all(isinstance(r, dict) for r in value)
                if not ok:
                    story.append(Paragraph(
                        f"[cannot display &quot;{escape(field['label'])}&quot;: content does not match "
                        f"the expected table shape]", st["error"]))
                else:
                    cols = field.get("columns", [])
                    cell_style = ParagraphStyle("cell", fontName=body, fontSize=9.5, leading=13, textColor="#1a1a1a")
                    head_style = ParagraphStyle("cellhead", fontName=bold, fontSize=9.5, leading=13, textColor="#1a1a1a")
                    data = [[Paragraph(c.capitalize(), head_style) for c in cols]] + [
                        [Paragraph(escape(str(r.get(c, ""))), cell_style) for c in cols] for r in value
                    ]
                    t = Table(data, hAlign="LEFT", colWidths=compute_col_widths(cols))
                    t.setStyle(TableStyle([
                        ("LINEBELOW", (0, 0), (-1, 0), 0.75, "#8a877d"),
                        ("LINEBELOW", (0, 1), (-1, -1), 0.4, "#c9c5bc"),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                        ("TOPPADDING", (0, 0), (-1, -1), 6),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ]))
                    story.append(t)
            elif shape == "boolean":
                story.append(Paragraph("Yes" if value else "No", text_style))
            else:
                story.append(Paragraph(f"[unrecognised shape: {escape(shape)}]", st["error"]))
            story.append(Spacer(1, 3))

    # ---- fixed footer, identical structure to the webpage's base frame ----
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=0.5, color="#c9c5bc", spaceAfter=8))
    if display_doi:
        story.append(Paragraph(
            f"Pages {article['pages']} &middot; https://doi.org/{escape(str(display_doi))}",
            st["footer"]))
    else:
        story.append(Paragraph(f"Pages {article['pages']}", st["footer"]))
    story.append(Paragraph(f"Licence: {escape(article['licence'])}", st["footer"]))

    doc = SimpleDocTemplate(out_path, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm, title=article["title"])
    doc.build(story)


if __name__ == "__main__":
    # Optional third arg: DOI override for embedding a reserved Zenodo DOI
    override = sys.argv[3] if len(sys.argv) > 3 else None
    build(sys.argv[1], sys.argv[2], doi_override=override)
    print(f"wrote {sys.argv[2]}" + (f" (doi={override})" if override else ""))
