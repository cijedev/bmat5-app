"""PDF progress report for admin/clinical use (ReportLab)."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Subtle BMW brand accent (warm amber on cool slate — matches app warning tone)
BRAND = colors.HexColor("#c9892e")
BRAND_SOFT = colors.HexColor("#f3e6cf")
INK = colors.HexColor("#1a1423")
MUTED = colors.HexColor("#5c5668")


def _p(text: str, style) -> Paragraph:
    return Paragraph(escape(text or "").replace("\n", "<br/>"), style)


def build_clinical_progress_pdf_bytes(
    *,
    display_name: str,
    masked_email: str,
    user_id: int,
    generated_at: datetime,
    wellness_score: int,
    wellness_label: str,
    assessments: list,
    checkins: list,
) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=64,
        bottomMargin=64,
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "BmwTitle",
        parent=styles["Title"],
        textColor=INK,
        fontSize=18,
        spaceAfter=4,
    )
    h2 = ParagraphStyle(
        "BmwH2",
        parent=styles["Heading2"],
        textColor=INK,
        fontSize=12,
        spaceBefore=8,
        spaceAfter=6,
    )
    body = ParagraphStyle("BmwBody", parent=styles["BodyText"], textColor=INK, fontSize=10)
    small = ParagraphStyle("BmwSmall", parent=styles["Normal"], textColor=MUTED, fontSize=9)
    footer_style = ParagraphStyle(
        "BmwFooter",
        parent=styles["Normal"],
        textColor=MUTED,
        fontSize=8,
        alignment=1,
    )
    story = []

    story.append(_p("Better Mental Wellness (BMW)", title))
    story.append(
        HRFlowable(width="100%", thickness=2, color=BRAND, spaceBefore=2, spaceAfter=8)
    )
    story.append(_p("User progress summary", h2))
    story.append(
        _p(f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M UTC')}", small)
    )
    story.append(Spacer(1, 0.12 * inch))

    story.append(_p("Participant", h2))
    story.append(_p(f"Display name: {display_name}", body))
    story.append(_p(f"Identifier (masked): {masked_email}", body))
    story.append(_p(f"Internal user id: {user_id}", body))
    story.append(Spacer(1, 0.12 * inch))
    story.append(_p(f"Wellness index (app): {wellness_score} — {wellness_label}", body))
    story.append(Spacer(1, 0.2 * inch))

    story.append(_p("Screenings (most recent first)", h2))
    a_rows = [["Kind", "Score", "Severity", "Item9", "Date"]]
    for a in assessments[:40]:
        i9 = "" if a.item9_score is None else str(a.item9_score)
        a_rows.append(
            [
                a.kind,
                str(a.total_score),
                a.severity[:32],
                i9,
                a.created_at.strftime("%Y-%m-%d %H:%M"),
            ]
        )
    if len(a_rows) == 1:
        a_rows.append(["—", "—", "—", "—", "No records"])
    t1 = Table(
        a_rows,
        repeatRows=1,
        colWidths=[0.9 * inch, 0.7 * inch, 1.4 * inch, 0.55 * inch, 1.55 * inch],
    )
    t1.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_SOFT),
                ("TEXTCOLOR", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 1), (-1, -1), INK),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8c4d0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 1, BRAND),
            ]
        )
    )
    story.append(t1)
    story.append(Spacer(1, 0.2 * inch))

    story.append(_p("Daily check-ins (most recent first)", h2))
    c_rows = [["Mood", "Stress", "Sleep (h)", "Date"]]
    for c in checkins[:40]:
        c_rows.append(
            [
                str(c.mood),
                str(c.stress),
                f"{c.sleep_hours:.1f}",
                c.created_at.strftime("%Y-%m-%d %H:%M"),
            ]
        )
    if len(c_rows) == 1:
        c_rows.append(["—", "—", "—", "No records"])
    t2 = Table(c_rows, repeatRows=1, colWidths=[0.85 * inch, 0.85 * inch, 1.0 * inch, 2.4 * inch])
    t2.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BRAND_SOFT),
                ("TEXTCOLOR", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 1), (-1, -1), INK),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#c8c4d0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LINEBELOW", (0, 0), (-1, 0), 1, BRAND),
            ]
        )
    )
    story.append(t2)
    story.append(Spacer(1, 0.28 * inch))
    story.append(
        HRFlowable(width="100%", thickness=0.8, color=BRAND, spaceBefore=4, spaceAfter=8)
    )
    story.append(_p("Not a diagnosis · For care coordination only", footer_style))
    story.append(
        _p(
            "BMW does not replace clinical judgment. Use this export in line with your organization’s privacy policy.",
            footer_style,
        )
    )
    story.append(
        _p(f"Generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')} · Better Mental Wellness (BMW)", footer_style)
    )

    doc.build(story)
    return buf.getvalue()
