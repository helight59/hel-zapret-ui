from __future__ import annotations

import datetime as dt
import logging
import re
from pathlib import Path
from typing import Callable

from src.cli.service_bat import run_tests_via_menu


log = logging.getLogger('tests')
ProgressCb = Callable[[dict[str, object]], None]

_RE_CFG_HDR = re.compile(r'^\s*\[(\d+)\s*/\s*(\d+)\]\s+(.+?\.bat)\s*$', re.I)
_RE_ANALYTICS_STD = re.compile(r'^\s*(.+?)\s*:\s*HTTP\s+OK:\s*(\d+),\s*ERR:\s*(\d+),\s*UNSUP:\s*(\d+),\s*Ping\s+OK:\s*(\d+),\s*Fail:\s*(\d+)\s*$', re.I)
_RE_ANALYTICS_DPI = re.compile(r'^\s*(.+?)\s*:\s*OK:\s*(\d+),\s*FAIL:\s*(\d+),\s*UNSUP:\s*(\d+),\s*BLOCKED:\s*(\d+)\s*$', re.I)
_RE_BEST_CFG = re.compile(r'^\s*Best\s+config:\s*(.+?)\s*$', re.I)
_RE_STEP = re.compile(r'^\s*>\s*(.+?)\s*$', re.I)


def run_menu_tests_multi(
    zapret_dir: Path,
    run_dir: Path,
    kind: str,
    configs: list[str],
    is_cancelled: Callable[[], bool] | None = None,
    on_progress: ProgressCb | None = None,
) -> tuple[dict[str, str], dict[str, str], dict[str, str], str, dict[str, tuple[int, ...]], str | None, bool]:
    started = dt.datetime.now()
    cancelled = is_cancelled or (lambda: False)
    progress = on_progress or (lambda _: None)
    idx_by_cfg = {cfg: index for index, cfg in enumerate(configs or [])}

    current_cfg: str | None = None
    current_batch = ''

    def handle_line(line: str) -> None:
        nonlocal current_cfg, current_batch
        text = (line or '').strip('\r')
        match = _RE_CFG_HDR.match(text.strip())
        if match:
            index = int(match.group(1))
            total = int(match.group(2))
            name = (match.group(3) or '').strip()
            current_cfg = name
            current_batch = f'{index}/{total}'
            if name in idx_by_cfg:
                progress({'phase': 'config', 'config': name, 'batch': current_batch})
            return

        step = _RE_STEP.match(text)
        if step and current_cfg and (current_cfg in idx_by_cfg):
            progress({'phase': 'step', 'config': current_cfg, 'batch': current_batch, 'step': (step.group(1) or '').strip()})

    log.info('tests service.bat start kind=%s configs=%d', kind, len(configs or []))
    result = run_tests_via_menu(
        zapret_dir,
        test_type=kind,
        configs=list(configs or []),
        total_timeout_s=1800.0,
        is_cancelled=cancelled,
        on_output_line=handle_line,
    )

    output = result.output or ''
    duration = (dt.datetime.now() - started).total_seconds()
    all_log_path = run_dir / f'{kind}_all.service_bat.txt'
    try:
        all_log_path.write_text(output, encoding='utf-8', errors='ignore')
    except Exception:
        pass

    blocks = split_test_output_by_config(output)
    analytics_block, analytics_map, best = parse_analytics(output, kind)

    statuses: dict[str, str] = {}
    log_paths: dict[str, str] = {}
    for cfg in configs or []:
        analytics = analytics_map.get(cfg)
        statuses[cfg] = status_from_analytics(analytics, kind)
        block = (blocks.get(cfg) or '').strip()
        log_path = run_dir / f'{kind}_{safe_name(cfg)}.service_bat.txt'
        try:
            log_path.write_text((block + '\n') if block else output, encoding='utf-8', errors='ignore')
        except Exception:
            pass
        log_paths[cfg] = str(log_path)
        blocks[cfg] = block

    cancelled_run = (result.message or '').lower() == 'cancelled' or cancelled()
    if (not cancelled_run) and (not result.ok):
        for cfg in configs or []:
            if statuses.get(cfg) == 'OK':
                statuses[cfg] = 'ERROR'

    log.info('tests service.bat done kind=%s ok=%s cancelled=%s duration_s=%s best="%s"', kind, bool(result.ok), bool(cancelled_run), round(duration, 2), str(best or ''))
    return statuses, log_paths, blocks, analytics_block, analytics_map, best, cancelled_run


def split_test_output_by_config(output: str) -> dict[str, str]:
    if not output:
        return {}
    lines = output.replace('\r', '').split('\n')
    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for raw in lines:
        text = (raw or '').rstrip('\n')
        match = _RE_CFG_HDR.match(text.strip())
        if match:
            current = (match.group(3) or '').strip()
            if current:
                blocks[current] = [text]
            continue
        if text.strip() in {'All tests finished.', '=== ANALYTICS ==='}:
            current = None
            continue
        if current and current in blocks:
            blocks[current].append(text)
    return {key: '\n'.join(value).strip() for key, value in blocks.items() if key and value}


def parse_analytics(output: str, kind: str) -> tuple[str, dict[str, tuple[int, ...]], str | None]:
    if not output:
        return '', {}, None

    lines = output.replace('\r', '').split('\n')
    start = -1
    for index, line in enumerate(lines):
        if (line or '').strip() == '=== ANALYTICS ===':
            start = index
            break
    if start == -1:
        return '', {}, find_best(output)

    end = len(lines)
    for index in range(start + 1, len(lines)):
        if (lines[index] or '').strip().lower().startswith('results saved to'):
            end = index
            break

    chunk = [line.rstrip() for line in lines[start:end] if line is not None]
    analytics_block = '\n'.join(chunk).strip()
    analytics_map: dict[str, tuple[int, ...]] = {}
    best: str | None = None

    for line in chunk:
        text = (line or '').strip()
        if not text:
            continue
        match_best = _RE_BEST_CFG.match(text)
        if match_best:
            best = (match_best.group(1) or '').strip()
            continue
        if (kind or '').lower() == 'standard':
            match = _RE_ANALYTICS_STD.match(text)
            if match:
                analytics_map[(match.group(1) or '').strip()] = (
                    int(match.group(2)),
                    int(match.group(3)),
                    int(match.group(4)),
                    int(match.group(5)),
                    int(match.group(6)),
                )
            continue
        match = _RE_ANALYTICS_DPI.match(text)
        if match:
            analytics_map[(match.group(1) or '').strip()] = (
                int(match.group(2)),
                int(match.group(3)),
                int(match.group(4)),
                int(match.group(5)),
            )

    if not best:
        best = find_best(analytics_block)
    return analytics_block, analytics_map, best


def find_best(text: str) -> str | None:
    best = None
    for line in (text or '').replace('\r', '').split('\n'):
        match = _RE_BEST_CFG.match((line or '').strip())
        if match:
            best = (match.group(1) or '').strip()
    return best


def status_from_analytics(analytics: tuple[int, ...] | None, kind: str) -> str:
    if not analytics:
        return 'DONE'
    if (kind or '').lower() == 'standard':
        if int(analytics[1]) == 0 and int(analytics[4]) == 0:
            return 'OK'
        return 'WARN'
    fail = int(analytics[1])
    blocked = int(analytics[3])
    if fail == 0 and blocked == 0:
        return 'OK'
    if fail > 0:
        return 'FAIL'
    return 'WARN'


def safe_name(value: str) -> str:
    text = (value or '').strip().lower()
    text = re.sub(r'[^a-z0-9._()\-]+', '_', text)
    text = re.sub(r'_+', '_', text).strip('_')
    return text or 'config'
