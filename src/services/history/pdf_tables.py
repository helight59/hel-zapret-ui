from __future__ import annotations

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, Table, TableStyle


from src.services.history.pdf_models import DpiAnalyticsRow, DpiTargetRow, StdAnalyticsRow, StdTargetResult


def make_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='TitleCenter', parent=styles['Title'], alignment=1, spaceAfter=10))
    styles.add(ParagraphStyle(name='H2', parent=styles['Heading2'], spaceBefore=10, spaceAfter=6))
    styles.add(ParagraphStyle(name='H3', parent=styles['Heading3'], spaceBefore=8, spaceAfter=4))
    styles.add(ParagraphStyle(name='Small', parent=styles['BodyText'], fontSize=9, leading=11))
    return styles


def build_meta_table(meta: list[tuple[str, str]], styles):
    data = [[Paragraph(f'<b>{esc(key)}</b>', styles['Small']), Paragraph(esc(value), styles['Small'])] for key, value in meta]
    table = Table(data, colWidths=[42 * mm, None])
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('BOX', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return table


def build_summary_table(rows: list[list[str]], styles):
    data: list[list[object]] = [['Config', 'Batch', 'Standard', 'DPI']]
    for row in rows or []:
        data.append([esc(cell) for cell in row])
    table = Table(data, colWidths=[None, 20 * mm, 22 * mm, 22 * mm], repeatRows=1)
    style = [
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]
    for index, row in enumerate(rows, start=1):
        style.append(('BACKGROUND', (0, index), (-1, index), colors.white if index % 2 else colors.whitesmoke))
        if len(row) > 2:
            style.append(('BACKGROUND', (2, index), (2, index), status_bg(row[2])))
        if len(row) > 3:
            style.append(('BACKGROUND', (3, index), (3, index), status_bg(row[3])))
    table.setStyle(TableStyle(style))
    return table


def badge(text: str, styles):
    table = Table([[Paragraph(f'<b>{esc(text)}</b>', styles['Small'])]], colWidths=[None])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.lavender),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    return table


def fmt_status(value: str | None, styles) -> Paragraph:
    text = (value or '').upper().strip()
    if text == 'ERROR':
        text = 'ERR'
    if not text:
        return Paragraph('', styles['Small'])
    color = 'black'
    if text == 'OK':
        color = 'green'
    elif text in {'ERR', 'FAIL', 'LIKELY_BLOCKED'}:
        color = 'red'
    elif text in {'UNSUP', 'UNSUPPORTED', 'DONE', 'CANCELLED'}:
        color = 'grey'
    return Paragraph(f'<font color="{color}"><b>{esc(text)}</b></font>', styles['Small'])


def std_results_table(rows: list[StdTargetResult], styles):
    data: list[list[object]] = [['Target', 'HTTP', 'TLS 1.2', 'TLS 1.3', 'Ping, ms']]
    for row in rows:
        data.append([
            Paragraph(esc(row.target), styles['Small']),
            fmt_status(row.http, styles),
            fmt_status(row.tls12, styles),
            fmt_status(row.tls13, styles),
            Paragraph(esc(str(row.ping_ms) if row.ping_ms is not None else ''), styles['Small']),
        ])
    return _simple_table(data, [52 * mm, 18 * mm, 18 * mm, 18 * mm, 20 * mm], 9)


def dpi_results_table(rows: list[DpiTargetRow], styles):
    data: list[list[object]] = [['Target', 'Provider', 'HTTP', 'TLS 1.2', 'TLS 1.3']]
    for row in rows:
        data.append([
            Paragraph(esc(row.target_id), styles['Small']),
            Paragraph(esc(row.provider), styles['Small']),
            fmt_status(row.http, styles),
            fmt_status(row.tls12, styles),
            fmt_status(row.tls13, styles),
        ])
    return _simple_table(data, [24 * mm, None, 18 * mm, 18 * mm, 18 * mm], 9)


def std_analytics_table(rows: list[StdAnalyticsRow], styles):
    data: list[list[object]] = [['Config', 'OK', 'ERR', 'UNSUP', 'OK %', 'Ping OK', 'Ping Fail', 'Ping OK %']]
    for row in rows:
        data.append([
            Paragraph(esc(row.config), styles['Small']),
            Paragraph(str(row.ok), styles['Small']),
            Paragraph(str(row.err), styles['Small']),
            Paragraph(str(row.unsup), styles['Small']),
            Paragraph(row.http_rate(), styles['Small']),
            Paragraph(str(row.ping_ok), styles['Small']),
            Paragraph(str(row.ping_fail), styles['Small']),
            Paragraph(row.ping_rate(), styles['Small']),
        ])
    return _simple_table(data, [None, 14 * mm, 14 * mm, 16 * mm, 16 * mm, 16 * mm, 18 * mm, 16 * mm], 8)


def dpi_analytics_table(rows: list[DpiAnalyticsRow], styles):
    data: list[list[object]] = [['Config', 'OK', 'FAIL', 'UNSUP', 'BLOCK', 'OK %']]
    for row in rows:
        data.append([
            Paragraph(esc(row.config), styles['Small']),
            Paragraph(str(row.ok), styles['Small']),
            Paragraph(str(row.fail), styles['Small']),
            Paragraph(str(row.unsup), styles['Small']),
            Paragraph(str(row.blocked), styles['Small']),
            Paragraph(row.ok_rate(), styles['Small']),
        ])
    return _simple_table(data, [None, 14 * mm, 16 * mm, 16 * mm, 16 * mm, 16 * mm], 8)


def warnings_box(warnings: list[str], styles):
    text = '<br/>'.join(esc(item) for item in warnings[:16])
    table = Table([[Paragraph('<b>Warnings</b>', styles['Small'])], [Paragraph(text, styles['Small'])]], colWidths=[None])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('BACKGROUND', (0, 1), (-1, 1), colors.lightyellow),
        ('BOX', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    return table


def status_bg(value: str) -> colors.Color:
    text = (value or '').upper().strip()
    if text == 'OK':
        return colors.lavender
    if text in {'WARN', 'WARNING'}:
        return colors.lightyellow
    if text in {'ERROR', 'FAIL', 'ERR', 'CANCELLED'}:
        return colors.mistyrose
    if text in {'DONE', '—', '-', 'N/A'}:
        return colors.whitesmoke
    return colors.white


def esc(value: str) -> str:
    return (value or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def _simple_table(data: list[list[object]], col_widths, font_size: int):
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), font_size),
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('LEFTPADDING', (0, 0), (-1, -1), 5 if font_size >= 9 else 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5 if font_size >= 9 else 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3 if font_size >= 9 else 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3 if font_size >= 9 else 2),
    ]))
    return table
