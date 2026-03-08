from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.cli.tests_patch import ensure_tests_cli_support
from src.services.history.pdf import export_run_pdf
from src.services.history.store import HistoryStore, StrategyResult, TestRun
from src.services.tests.runner_parse import run_menu_tests_multi
from src.services.tests.runner_state import UpdateCheckGuard, remove_zapret_before_tests, restore_zapret_after_tests, snapshot_zapret_state
from src.services.zapret.layout import ZapretLayout


log = logging.getLogger('tests')


@dataclass
class RunOptions:
    standard: bool
    dpi: bool
    strategies: list[str]


ProgressCb = Callable[[dict[str, object]], None]


def run_tests(
    zapret_dir: Path,
    data_dir: Path,
    opts: RunOptions,
    on_row_updated: Callable[[int], None] | None = None,
    on_progress: ProgressCb | None = None,
    is_cancelled: Callable[[], bool] | None = None,
) -> tuple[str, str]:
    row = on_row_updated or (lambda _: None)
    progress = on_progress or (lambda _: None)
    cancelled = is_cancelled or (lambda: False)
    guard = UpdateCheckGuard(zapret_dir)

    try:
        log.info('tests start standard=%s dpi=%s strategies=%d', bool(opts.standard), bool(opts.dpi), len(opts.strategies or []))
        layout = ZapretLayout(zapret_dir)
        if not layout.ok():
            return 'ERROR', 'zapret layout invalid'

        ok_patch, msg_patch = ensure_tests_cli_support(zapret_dir)
        log.info('tests cli patch ok=%s msg="%s"', bool(ok_patch), str(msg_patch or ''))
        if not ok_patch:
            return 'ERROR', 'не удалось подготовить zapret для автоматических тестов: ' + (msg_patch or '')

        guard.disable()

        store = HistoryStore(data_dir)
        run_dir = store.new_run_dir()
        started = dt.datetime.now().isoformat(timespec='seconds')
        snapshot = snapshot_zapret_state(zapret_dir, data_dir)
        log.info(
            'tests snapshot installed=%s service_state=%s capture_running=%s strategy="%s" external=%s start_mode=%s',
            bool(snapshot.get('installed')),
            str(snapshot.get('service_state') or ''),
            bool(snapshot.get('capture_running')),
            str(snapshot.get('strategy') or ''),
            bool(snapshot.get('external')),
            str(snapshot.get('start_mode') or ''),
        )

        removed_ok, removed_msg = remove_zapret_before_tests(zapret_dir, data_dir, snapshot)
        if not removed_ok:
            return 'ERROR', removed_msg

        results: list[StrategyResult] = []
        full_log: list[str] = []
        restore: dict[str, object] = {}
        selected: list[str] = []
        cancelled_run = False

        try:
            selected = _select_strategies(layout.list_strategies(), opts.strategies)
            log.info('tests selected strategies=%d (available=%d)', len(selected), len(layout.list_strategies()))
            idx_by_cfg = {name: index for index, name in enumerate(selected)}

            std_status: dict[str, str] = {}
            std_logs: dict[str, str] = {}
            std_blocks: dict[str, str] = {}
            std_analytics = ''
            std_map: dict[str, tuple[int, ...]] = {}
            std_best: str | None = None

            dpi_status: dict[str, str] = {}
            dpi_logs: dict[str, str] = {}
            dpi_blocks: dict[str, str] = {}
            dpi_analytics = ''
            dpi_map: dict[str, tuple[int, ...]] = {}
            dpi_best: str | None = None

            def on_line(kind: str):
                def callback(event: dict[str, object]) -> None:
                    cfg = (event.get('config') or '') if isinstance(event.get('config'), str) else ''
                    if cfg and cfg in idx_by_cfg:
                        event['row'] = idx_by_cfg[cfg]
                    event['kind'] = kind
                    progress(event)
                return callback

            if opts.standard and selected and (not cancelled()):
                std_status, std_logs, std_blocks, std_analytics, std_map, std_best, cancelled_run = run_menu_tests_multi(
                    zapret_dir,
                    run_dir,
                    'standard',
                    selected,
                    is_cancelled=cancelled,
                    on_progress=on_line('standard'),
                )
                _append_blocks(full_log, selected, std_blocks, 'STANDARD')
                if std_analytics:
                    full_log.append(f'=== Analytics STANDARD ===\n{std_analytics}\n')

            if (not cancelled_run) and opts.dpi and selected and (not cancelled()):
                dpi_status, dpi_logs, dpi_blocks, dpi_analytics, dpi_map, dpi_best, cancelled_run = run_menu_tests_multi(
                    zapret_dir,
                    run_dir,
                    'dpi',
                    selected,
                    is_cancelled=cancelled,
                    on_progress=on_line('dpi'),
                )
                _append_blocks(full_log, selected, dpi_blocks, 'DPI')
                if dpi_analytics:
                    full_log.append(f'=== Analytics DPI ===\n{dpi_analytics}\n')

            if cancelled() or cancelled_run:
                cancelled_run = True

            for index, name in enumerate(selected):
                result = _build_strategy_result(
                    index=index,
                    total=len(selected),
                    name=name,
                    opts=opts,
                    cancelled_run=cancelled_run,
                    std_status=std_status,
                    dpi_status=dpi_status,
                    std_logs=std_logs,
                    dpi_logs=dpi_logs,
                    std_map=std_map,
                    dpi_map=dpi_map,
                    std_best=std_best,
                    dpi_best=dpi_best,
                )
                results.append(result)
                row(index)
        finally:
            restore = restore_zapret_after_tests(zapret_dir, data_dir, snapshot)
            log.info('tests restore ok=%s msg="%s"', bool(restore.get('ok')), str(restore.get('message') or ''))

        finished = dt.datetime.now().isoformat(timespec='seconds')
        pdf_path = run_dir / 'report.pdf'
        meta = [
            ('Run ID', run_dir.name),
            ('Started', started),
            ('Finished', finished),
            ('Zapret local version', layout.local_version() or '-'),
            ('Standard', 'ON' if opts.standard else 'OFF'),
            ('DPI', 'ON' if opts.dpi else 'OFF'),
            ('Cancelled', 'YES' if cancelled_run else 'NO'),
            ('Zapret was installed', 'YES' if snapshot.get('installed') else 'NO'),
            ('Zapret was running', 'YES' if snapshot.get('was_running') else 'NO'),
            ('Zapret restore', 'OK' if restore.get('ok') else 'FAIL'),
        ]
        table_rows = [[item.name, item.batch, item.standard, item.dpi] for item in results]
        export_run_pdf(pdf_path, 'hel zapret ui test report', meta, table_rows, '\n'.join(full_log))

        run_obj = TestRun(
            run_id=run_dir.name,
            started_at=started,
            finished_at=finished,
            zapret_version_local=layout.local_version() or '',
            standard_enabled=opts.standard,
            dpi_enabled=opts.dpi,
            selected_strategies=selected,
            results=results,
            pdf_path=str(pdf_path),
            restore=restore,
        )
        store.write_run(run_dir, run_obj)
        log.info('tests finished ok run_dir=%s cancelled=%s', str(run_dir), bool(cancelled_run))
        return ('CANCELLED', str(run_dir)) if cancelled_run else ('OK', str(run_dir))
    except Exception as exc:
        log.exception('tests failed')
        return 'ERROR', str(exc)
    finally:
        guard.restore()


def _select_strategies(all_bats: list[str], picked: list[str]) -> list[str]:
    selected: list[str] = []
    seen: set[str] = set()
    for strategy in picked or []:
        if strategy not in all_bats or strategy in seen:
            continue
        seen.add(strategy)
        selected.append(strategy)
    return selected


def _append_blocks(target: list[str], selected: list[str], blocks: dict[str, str], suffix: str) -> None:
    for name in selected:
        block = blocks.get(name, '')
        if block:
            target.append(f'=== {name} {suffix} ===\n{block}\n')


def _build_strategy_result(
    index: int,
    total: int,
    name: str,
    opts: RunOptions,
    cancelled_run: bool,
    std_status: dict[str, str],
    dpi_status: dict[str, str],
    std_logs: dict[str, str],
    dpi_logs: dict[str, str],
    std_map: dict[str, tuple[int, ...]],
    dpi_map: dict[str, tuple[int, ...]],
    std_best: str | None,
    dpi_best: str | None,
) -> StrategyResult:
    standard = std_status.get(name, 'NOT_SELECTED')
    dpi = dpi_status.get(name, 'NOT_SELECTED')
    if opts.standard and standard == 'NOT_SELECTED':
        standard = 'CANCELLED' if cancelled_run else 'DONE'
    if not opts.standard:
        standard = '—'
    if opts.dpi and dpi == 'NOT_SELECTED':
        dpi = 'CANCELLED' if cancelled_run else 'DONE'
    if not opts.dpi:
        dpi = '—'

    result = StrategyResult(
        name=name,
        batch=f'{index + 1}/{total}',
        standard=standard,
        dpi=dpi,
        duration_s=0.0,
        log_standard=std_logs.get(name, ''),
        log_dpi=dpi_logs.get(name, ''),
    )

    analytics_std = std_map.get(name)
    analytics_dpi = dpi_map.get(name)
    if analytics_std and len(analytics_std) >= 5:
        result.std_http_ok = int(analytics_std[0])
        result.std_http_err = int(analytics_std[1])
        result.std_http_unsup = int(analytics_std[2])
        result.std_ping_ok = int(analytics_std[3])
        result.std_ping_fail = int(analytics_std[4])
    if analytics_dpi and len(analytics_dpi) >= 4:
        result.dpi_ok = int(analytics_dpi[0])
        result.dpi_fail = int(analytics_dpi[1])
        result.dpi_unsup = int(analytics_dpi[2])
        result.dpi_blocked = int(analytics_dpi[3])
    if std_best and std_best.strip() == name.strip():
        result.best_standard = True
    if dpi_best and dpi_best.strip() == name.strip():
        result.best_dpi = True
    return result
