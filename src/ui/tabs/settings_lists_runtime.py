from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QTimer

from src.services.zapret.service import ZapretService
from src.ui.adapters.fn_worker import FnWorker
from src.ui.adapters.state_worker import StateWorker


def read_runtime_snapshot(cfg) -> dict[str, object]:
    enabled = False
    try:
        service = ZapretService(Path(cfg.zapret_dir), Path(cfg.data_dir))
        status = service.status()
        enabled = (status.service_state == 'RUNNING') or status.capture_running
    except Exception:
        enabled = False
    return {'enabled': enabled}


def refresh_runtime_state_async(tab) -> None:
    if tab._runtime_thread:
        tab._pending_runtime_refresh = True
        return
    tab._runtime_thread = QThread()
    tab._runtime_worker = StateWorker(lambda: read_runtime_snapshot(tab.cfg))
    tab._runtime_worker.moveToThread(tab._runtime_thread)
    tab._runtime_thread.started.connect(tab._runtime_worker.run)
    tab._runtime_worker.done.connect(tab._on_runtime_refresh_done)
    tab._runtime_worker.error.connect(tab._on_runtime_refresh_error)
    tab._runtime_thread.start()


def clear_runtime_worker(tab) -> None:
    if tab._runtime_thread:
        tab._runtime_thread.quit()
        tab._runtime_thread.wait(2000)
    tab._runtime_thread = None
    tab._runtime_worker = None


def restart_now(tab) -> None:
    if tab._busy or tab._restart_thread or (not tab._runtime_enabled):
        tab._sync_ui(applied_to_zapret=None)
        return

    tab._restart_thread = QThread()
    service = ZapretService(Path(tab.cfg.zapret_dir), Path(tab.cfg.data_dir))
    tab._restart_worker = FnWorker(lambda: service.restart(tab.cfg.last_strategy or ''))
    tab._restart_worker.moveToThread(tab._restart_thread)
    tab._restart_thread.started.connect(tab._restart_worker.run)
    tab._restart_worker.done.connect(tab._on_restart_done)
    tab._restart_thread.start()
    tab._set_busy(True, 'Перезапускаем zapret...')
    tab._sync_ui(applied_to_zapret=None)


def service_sync_timeout(tab) -> None:
    if not tab._post_restart_sync:
        return
    tab.on_service_sync_finished()


def finish_restart(tab, ok: bool, msg: str) -> None:
    if tab._restart_thread:
        tab._restart_thread.quit()
        tab._restart_thread.wait(2000)
    tab._restart_thread = None
    tab._restart_worker = None

    if not ok:
        tab._last_error = ('Не удалось перезапустить zapret. ' + (msg or 'Проверь логи приложения.')).strip()
        tab._last_status_text = ''
        refresh_runtime_state_async(tab)
        tab._set_busy(False, '')
        tab._sync_ui(applied_to_zapret=None)
        return

    tab._post_restart_sync = True
    tab.appStatusChanged.emit('Проверяем статус...')
    tab.serviceSyncRequested.emit()
    QTimer.singleShot(4000, tab._service_sync_timeout)
