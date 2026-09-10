"""Render PROJECT_REPORT.md as a submission-ready PDF with project visuals."""

from __future__ import annotations

import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "PROJECT_REPORT.md"
OUTPUT = ROOT / "PROJECT_REPORT.pdf"
ARCHITECTURE = ROOT / "authguard_architecture.png"
RESULTS_CHART = ROOT / "stage4_asr_utility.png"


def inline_markup(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"`(.+?)`", r"<font name='Courier'>\1</font>", text)
    return text


def image(path: Path, width: float) -> Image:
    result = Image(str(path), width=width, height=width * 0.625)
    result.hAlign = "CENTER"
    return result


def build_story() -> list:
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=23, leading=28, alignment=TA_CENTER, textColor=colors.HexColor("#123047"),
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="Subtitle", parent=styles["Normal"], fontName="Helvetica",
        fontSize=11, leading=15, alignment=TA_CENTER, textColor=colors.HexColor("#52606d"),
        spaceAfter=16,
    ))
    styles.add(ParagraphStyle(
        name="H1Report", parent=styles["Heading1"], fontName="Helvetica-Bold",
        fontSize=16, leading=20, textColor=colors.HexColor("#123047"),
        spaceBefore=14, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="H2Report", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=12, leading=15, textColor=colors.HexColor("#1f5f7a"),
        spaceBefore=10, spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="BodyReport", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=9.3, leading=13.5, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="BulletReport", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=9.3, leading=13.5, leftIndent=14, firstLineIndent=-8, spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="Caption", parent=styles["Normal"], fontName="Helvetica-Oblique",
        fontSize=8, leading=10, alignment=TA_CENTER, textColor=colors.HexColor("#52606d"),
        spaceBefore=4, spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="TableCell", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=8, leading=10,
    ))
    styles.add(ParagraphStyle(
        name="TableHeader", parent=styles["TableCell"], fontName="Helvetica-Bold",
        textColor=colors.white,
    ))

    story = []
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    index = 0
    in_code = False
    code_lines = []

    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            if in_code:
                story.append(Preformatted("\n".join(code_lines), styles["Code"]))
                story.append(Spacer(1, 6))
                code_lines = []
                in_code = False
            else:
                in_code = True
            index += 1
            continue
        if in_code:
            code_lines.append(line)
            index += 1
            continue
        if not line.strip():
            index += 1
            continue

        if line.startswith("# "):
            story.append(Paragraph(inline_markup(line[2:]), styles["ReportTitle"]))
            story.append(Paragraph("Professional project report | AuthGuard research testbed", styles["Subtitle"]))
            if ARCHITECTURE.exists():
                story.append(image(ARCHITECTURE, 6.7 * inch))
                story.append(Paragraph("Figure 1. AuthGuard processing flow and provenance boundary.", styles["Caption"]))
            index += 1
            continue
        if line.startswith("## "):
            heading = line[3:]
            story.append(Paragraph(inline_markup(heading), styles["H1Report"]))
            if heading.startswith("8. Results") and RESULTS_CHART.exists():
                story.append(image(RESULTS_CHART, 6.5 * inch))
                story.append(Paragraph("Figure 2. Stage 2 baseline versus Stage 3 provenance defense.", styles["Caption"]))
            index += 1
            continue
        if line.startswith("### "):
            story.append(Paragraph(inline_markup(line[4:]), styles["H2Report"]))
            index += 1
            continue
        if line.startswith("> "):
            story.append(Paragraph(f"<i>{inline_markup(line[2:])}</i>", styles["BodyReport"]))
            index += 1
            continue
        if line.startswith("- ") or re.match(r"^\d+\. ", line):
            prefix = "&#8226; " if line.startswith("- ") else re.match(r"^\d+\. ", line).group(0)
            content = line[2:] if line.startswith("- ") else re.sub(r"^\d+\. ", "", line)
            story.append(Paragraph(prefix + inline_markup(content), styles["BulletReport"]))
            index += 1
            continue
        if line.startswith("| "):
            table_lines = []
            while index < len(lines) and lines[index].startswith("|"):
                if not re.match(r"^\|\s*:?-+", lines[index]):
                    table_lines.append([cell.strip() for cell in lines[index].strip().strip("|").split("|")])
                index += 1
            if table_lines:
                header = [Paragraph(inline_markup(cell), styles["TableHeader"]) for cell in table_lines[0]]
                body = [[Paragraph(inline_markup(cell), styles["TableCell"]) for cell in row] for row in table_lines[1:]]
                table = Table([header] + body, repeatRows=1, hAlign="CENTER")
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f5f7a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#b7c4cc")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef5f7")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]))
                story.append(table)
                story.append(Spacer(1, 7))
            continue
        story.append(Paragraph(inline_markup(line), styles["BodyReport"]))
        index += 1

    return story


def add_page_number(canvas, document) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#52606d"))
    canvas.drawString(0.7 * inch, 0.45 * inch, "AuthGuard | Provenance-tagged memory security testbed")
    canvas.drawRightString(A4[0] - 0.7 * inch, 0.45 * inch, f"Page {document.page}")
    canvas.restoreState()


def main() -> None:
    document = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4, rightMargin=0.7 * inch, leftMargin=0.7 * inch,
        topMargin=0.65 * inch, bottomMargin=0.7 * inch,
        title="AuthGuard Project Report", author="AuthGuard Project",
    )
    document.build(build_story(), onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(f"Created {OUTPUT}")


if __name__ == "__main__":
    main()
