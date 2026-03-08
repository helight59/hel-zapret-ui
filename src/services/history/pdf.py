from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from src.services.history.pdf_parse import parse_excerpt
from src.services.history.pdf_tables import (
    badge,
    build_meta_table,
    build_summary_table,
    dpi_analytics_table,
    dpi_results_table,
    esc,
    make_styles,
    std_analytics_table,
    std_results_table,
)


def export_run_pdf(pdf_path: Path, title: str, meta: list[tuple[str, str]], table_rows: list[list[str]], log_excerpt: str) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    styles = make_styles()
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=title,
    )

    parsed = parse_excerpt(log_excerpt)
    story: list[object] = [Paragraph(esc(title), styles['TitleCenter'])]

    story.append(Paragraph('Analytics', styles['H2']))
    if parsed['std_analytics_rows']:
        story.append(Paragraph('Standard', styles['H3']))
        story.append(std_analytics_table(parsed['std_analytics_rows'], styles))
        if parsed['std_best']:
            story.append(Spacer(1, 6))
            story.append(badge(f'Best config (Standard): {parsed["std_best"]}', styles))
        story.append(Spacer(1, 10))
    if parsed['dpi_analytics_rows']:
        story.append(Paragraph('DPI', styles['H3']))
        story.append(dpi_analytics_table(parsed['dpi_analytics_rows'], styles))
        if parsed['dpi_best']:
            story.append(Spacer(1, 6))
            story.append(badge(f'Best config (DPI): {parsed["dpi_best"]}', styles))
        story.append(Spacer(1, 10))

    story.append(Paragraph('Run info', styles['H2']))
    story.append(build_meta_table(meta, styles))
    story.append(Spacer(1, 10))
    story.append(Paragraph('Summary', styles['H2']))
    story.append(build_summary_table(table_rows, styles))
    story.append(Spacer(1, 10))
    story.append(Paragraph('Details', styles['H2']))

    for name in [row[0] for row in (table_rows or []) if row and row[0]]:
        section = parsed['by_config'].get(name) or {}
        story.append(Spacer(1, 10))
        story.append(Paragraph(esc(name), styles['Heading2']))

        standard = section.get('standard')
        if standard and standard.get('results'):
            story.append(Paragraph('Standard tests', styles['H3']))
            story.append(std_results_table(standard['results'], styles))
        elif standard:
            story.append(Paragraph('Standard tests', styles['H3']))
            story.append(Paragraph('No target results found.', styles['Small']))

        dpi = section.get('dpi')
        if dpi and dpi.get('rows'):
            story.append(Spacer(1, 10))
            story.append(Paragraph('DPI checkers', styles['H3']))
            story.append(dpi_results_table(dpi['rows'], styles))
        elif dpi:
            story.append(Spacer(1, 10))
            story.append(Paragraph('DPI checkers', styles['H3']))
            story.append(Paragraph('No DPI results found.', styles['Small']))

    doc.build(story, onFirstPage=_draw_footer, onLaterPages=_draw_footer)


def _draw_footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(doc.leftMargin, 12 * mm, 'hel zapret ui')
    canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 12 * mm, f'Page {canvas.getPageNumber()}')
    canvas.restoreState()
