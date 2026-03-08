from __future__ import annotations

import re

from src.services.history.pdf_models import DpiAnalyticsRow, DpiTargetRow, StdAnalyticsRow, StdTargetResult


RE_SECTION = re.compile(r'(?m)^\s*===\s*(.+?)\s+(STANDARD|DPI)\s*===\s*$')
RE_ANAL_HDR = re.compile(r'(?m)^\s*===\s*Analytics\s+(STANDARD|DPI)\s*===\s*$')
RE_STD_FULL = re.compile(r'^\s*(\S+)\s+HTTP:(\w+)\s+TLS1\.2:(\w+)\s+TLS1\.3:(\w+)\s*\|\s*Ping:\s*(\d+)\s*ms\s*$', re.I)
RE_STD_PING = re.compile(r'^\s*(\S+)\s+Ping:\s*(\d+)\s*ms\s*$', re.I)
RE_ANALYTICS_STD = re.compile(r'^\s*(.+?)\s*:\s*HTTP\s+OK:\s*(\d+),\s*ERR:\s*(\d+),\s*UNSUP:\s*(\d+),\s*Ping\s+OK:\s*(\d+),\s*Fail:\s*(\d+)\s*$', re.I)
RE_ANALYTICS_DPI = re.compile(r'^\s*(.+?)\s*:\s*OK:\s*(\d+),\s*FAIL:\s*(\d+),\s*UNSUP:\s*(\d+),\s*BLOCKED:\s*(\d+)\s*$', re.I)
RE_BEST = re.compile(r'^\s*Best\s+config:\s*(.+?)\s*$', re.I)
RE_DPI_TARGET = re.compile(r'^\s*===\s*(.+?)\s*\[(.+?)\]\s*===\s*$', re.I)
RE_DPI_LINE = re.compile(r'^\s*\[([^\]]+)\]\[([^\]]+)\].*?status=([A-Z_]+)\s*$', re.I)
NOISE_EXACT = {
    'Select test type:',
    'Select test run mode:',
    'Available configs:',
    'Press any key to close...',
    'All tests finished.',
    '=== ANALYTICS ===',
}


def parse_excerpt(text: str) -> dict[str, object]:
    lines = (text or '').replace('\r', '').split('\n')
    by_config: dict[str, dict[str, object]] = {}
    std_analytics_rows: list[StdAnalyticsRow] = []
    dpi_analytics_rows: list[DpiAnalyticsRow] = []
    std_best: str | None = None
    dpi_best: str | None = None
    current: tuple[str, str, str] | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, std_best, dpi_best
        if not current:
            buf = []
            return
        kind, first, second = current
        chunk = '\n'.join(buf).strip()
        if kind == 'analytics':
            if first == 'STANDARD':
                rows, best = parse_std_analytics(chunk)
                std_analytics_rows.extend(rows)
                std_best = best or std_best
            else:
                rows, best = parse_dpi_analytics(chunk)
                dpi_analytics_rows.extend(rows)
                dpi_best = best or dpi_best
        elif kind == 'section':
            section = by_config.setdefault(first, {})
            if second == 'STANDARD':
                section['standard'] = parse_standard_section(chunk)
            else:
                section['dpi'] = parse_dpi_section(chunk)
        buf = []

    for line in lines:
        match_analytics = RE_ANAL_HDR.match((line or '').strip())
        if match_analytics:
            flush()
            current = ('analytics', match_analytics.group(1).strip().upper(), '')
            buf = []
            continue
        match_section = RE_SECTION.match((line or '').strip())
        if match_section:
            flush()
            current = ('section', (match_section.group(1) or '').strip(), (match_section.group(2) or '').strip().upper())
            buf = []
            continue
        if current:
            buf.append(line)
    flush()

    return {
        'by_config': by_config,
        'std_analytics_rows': std_analytics_rows,
        'dpi_analytics_rows': dpi_analytics_rows,
        'std_best': std_best,
        'dpi_best': dpi_best,
    }


def parse_std_analytics(chunk: str) -> tuple[list[StdAnalyticsRow], str | None]:
    rows: list[StdAnalyticsRow] = []
    best: str | None = None
    for raw in (chunk or '').splitlines():
        line = (raw or '').strip()
        if not line or line in NOISE_EXACT:
            continue
        match_best = RE_BEST.match(line)
        if match_best:
            best = (match_best.group(1) or '').strip()
            continue
        match = RE_ANALYTICS_STD.match(line)
        if match:
            rows.append(StdAnalyticsRow(
                config=(match.group(1) or '').strip(),
                ok=int(match.group(2)),
                err=int(match.group(3)),
                unsup=int(match.group(4)),
                ping_ok=int(match.group(5)),
                ping_fail=int(match.group(6)),
            ))
    return rows, best


def parse_dpi_analytics(chunk: str) -> tuple[list[DpiAnalyticsRow], str | None]:
    rows: list[DpiAnalyticsRow] = []
    best: str | None = None
    for raw in (chunk or '').splitlines():
        line = (raw or '').strip()
        if not line or line in NOISE_EXACT:
            continue
        match_best = RE_BEST.match(line)
        if match_best:
            best = (match_best.group(1) or '').strip()
            continue
        match = RE_ANALYTICS_DPI.match(line)
        if match:
            rows.append(DpiAnalyticsRow(
                config=(match.group(1) or '').strip(),
                ok=int(match.group(2)),
                fail=int(match.group(3)),
                unsup=int(match.group(4)),
                blocked=int(match.group(5)),
            ))
    return rows, best


def parse_standard_section(chunk: str) -> dict[str, object]:
    results: list[StdTargetResult] = []
    warnings: list[str] = []
    for raw in (chunk or '').splitlines():
        line = (raw or '').strip()
        if not line or line in NOISE_EXACT or line.startswith('Results saved to') or line.startswith('>'):
            continue
        if line.startswith('[') and (']' in line) and (line.upper().startswith('[OK]') or line.upper().startswith('[INFO]')):
            continue
        if line.upper().startswith('[WARN]') or line.upper().startswith('[WARNING]') or 'timed out' in line.lower():
            warnings.append(line)
            continue
        match = RE_STD_FULL.match(line)
        if match:
            results.append(StdTargetResult(match.group(1), match.group(2), match.group(3), match.group(4), int(match.group(5))))
            continue
        match_ping = RE_STD_PING.match(line)
        if match_ping:
            results.append(StdTargetResult(match_ping.group(1), None, None, None, int(match_ping.group(2))))
    return {'results': results, 'warnings': warnings}


def parse_dpi_section(chunk: str) -> dict[str, object]:
    warnings: list[str] = []
    order: list[str] = []
    rows: dict[str, DpiTargetRow] = {}
    current_target = ''
    current_provider = ''

    for raw in (chunk or '').splitlines():
        line = (raw or '').strip()
        if not line or line in NOISE_EXACT or line.startswith('Results saved to') or line.startswith('>') or line.upper().startswith('[INFO]'):
            continue
        if line.upper().startswith('[WARN]') or line.upper().startswith('[WARNING]') or 'Pattern matches 16-20KB freeze' in line or 'Detected possible DPI' in line:
            warnings.append(line)
            continue
        match_target = RE_DPI_TARGET.match(line)
        if match_target:
            current_target = (match_target.group(1) or '').strip()
            current_provider = (match_target.group(2) or '').strip()
            key = f'{current_target}|{current_provider}'
            if key not in rows:
                rows[key] = DpiTargetRow(target_id=current_target, provider=current_provider)
                order.append(key)
            continue
        match_line = RE_DPI_LINE.match(line)
        if not match_line:
            continue
        target_id = (match_line.group(1) or '').strip()
        label = (match_line.group(2) or '').strip().upper()
        status = (match_line.group(3) or '').strip().upper()
        key = f'{current_target}|{current_provider}' if current_target and current_provider else f'{target_id}|{current_provider or ""}'
        if key not in rows:
            rows[key] = DpiTargetRow(target_id=target_id or current_target, provider=current_provider or '')
            order.append(key)
        row = rows[key]
        if label == 'HTTP':
            row.http = status
        elif label in {'TLS1.2', 'TLS 1.2', 'TLS12'}:
            row.tls12 = status
        elif label in {'TLS1.3', 'TLS 1.3', 'TLS13'}:
            row.tls13 = status
    return {'rows': [rows[key] for key in order if key in rows], 'warnings': warnings}
