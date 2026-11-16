from pathlib import Path
import re
import shutil
import html

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)

root = Path(__file__).resolve().parents[1]
md_path = root / "reports" / "assignment_report.md"
pdf_path = root / "reports" / "assignment_report.pdf"

if not md_path.exists():
    raise FileNotFoundError(md_path)

if pdf_path.exists():
    backup = pdf_path.with_name("assignment_report_backup.pdf")
    shutil.copy2(pdf_path, backup)
    print("Old PDF backup saved:", backup.name)

styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="ReportTitle", parent=styles["Title"],
    fontSize=19, leading=24, alignment=TA_CENTER,
    textColor=colors.HexColor("#183B56"), spaceAfter=18
))
styles.add(ParagraphStyle(
    name="SectionHeading", parent=styles["Heading2"],
    fontSize=14, leading=18, textColor=colors.HexColor("#183B56"),
    spaceBefore=12, spaceAfter=7
))
styles.add(ParagraphStyle(
    name="SubHeading", parent=styles["Heading3"],
    fontSize=11, leading=14, spaceBefore=8, spaceAfter=5
))
styles.add(ParagraphStyle(
    name="ReportBody", parent=styles["BodyText"],
    fontSize=9, leading=13, spaceAfter=7
))
styles.add(ParagraphStyle(
    name="ReportBullet", parent=styles["BodyText"],
    fontSize=9, leading=13, leftIndent=14,
    firstLineIndent=-8, spaceAfter=5
))
styles.add(ParagraphStyle(
    name="TableText", parent=styles["BodyText"],
    fontSize=7.5, leading=10
))

def inline_markup(value):
    value = html.escape(value, quote=False)
    value = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"`(.+?)`", r'<font name="Courier">\1</font>', value)
    return value

def table_cells(line):
    return [x.strip() for x in line.strip().strip("|").split("|")]

lines = md_path.read_text(encoding="utf-8-sig").splitlines()
story = []
paragraph = []
first_title = True

def flush_paragraph():
    if paragraph:
        story.append(Paragraph(
            inline_markup(" ".join(paragraph)), styles["ReportBody"]
        ))
        paragraph.clear()

i = 0
while i < len(lines):
    line = lines[i].strip()

    if not line:
        flush_paragraph()
        i += 1
        continue

    if line.startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i + 1]):
        flush_paragraph()
        raw_rows = [table_cells(line)]
        i += 2
        while i < len(lines) and lines[i].strip().startswith("|"):
            raw_rows.append(table_cells(lines[i]))
            i += 1

        data = [[Paragraph(inline_markup(c), styles["TableText"]) for c in row]
                for row in raw_rows]
        col_count = max(len(row) for row in data)
        data = [row + [""] * (col_count - len(row)) for row in data]

        table = Table(data, repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#183B56")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C7D1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F1F5F8")]),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.extend([table, Spacer(1, 10)])
        continue

    if line.startswith("# "):
        flush_paragraph()
        title = line[2:]
        story.append(Paragraph(inline_markup(title), styles["ReportTitle"]))
        first_title = False
    elif line.startswith("## "):
        flush_paragraph()
        story.append(Paragraph(inline_markup(line[3:]), styles["SectionHeading"]))
    elif line.startswith("### "):
        flush_paragraph()
        story.append(Paragraph(inline_markup(line[4:]), styles["SubHeading"]))
    elif line.startswith("- ") or line.startswith("* "):
        flush_paragraph()
        story.append(Paragraph("• " + inline_markup(line[2:]), styles["ReportBullet"]))
    else:
        paragraph.append(line)

    i += 1

flush_paragraph()

def footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(20 * mm, 12 * mm, "PACK EFY Assistant - Module 08")
    canvas.drawRightString(190 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()

doc = SimpleDocTemplate(
    str(pdf_path), pagesize=A4,
    rightMargin=18 * mm, leftMargin=18 * mm,
    topMargin=18 * mm, bottomMargin=20 * mm,
    title="PACK EFY Assistant - Module 08 Enterprise RAG Report",
    author="PACK EFY"
)
doc.build(story, onFirstPage=footer, onLaterPages=footer)

print("PDF generated successfully:", pdf_path)
print("Markdown lines:", len(lines))
print("PDF size:", pdf_path.stat().st_size, "bytes")
