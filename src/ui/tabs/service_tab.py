from __future__ import annotations

import logging

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import QMessageBox, QWidget

from src.app.config import AppConfig
from src.ui.adapters.state_worker import StateWorker
from src.ui.controllers.service_controller import HomeState, ServiceController
from src.ui.tabs.service_tab_actions import apply_strategy, install_zapret, on_action_done, remove_goodbye, remove_services, run_action, toggle_requested
from src.ui.tabs.service_tab_state import apply_state, emit_tray_state, handle_post_state, handle_settle_state
from src.ui.tabs.service_tab_view import build_service_tab, init_background, paint_background, set_combo_value, update_background, update_strategy_width


log = logging.getLogger('ui.service')


class ServiceTab(QWidget):
    enabledChanged = Signal(bool)
    notifyRequested = Signal(str, str)
    appStatusChanged = Signal(str)
    trayStateChanged = Signal(object)
    stateRefreshed = Signal()

    def __init__(self, cfg: AppConfig, initial_state: HomeState | None = None):
        super().__init__()
        self.cfg = cfg
        self.ctrl = ServiceController(cfg)

        self._state: HomeState | None = None
        self._selected_strategy = ''
        self._user_picked_strategy = False

        self._refresh_thread: QThread | None = None
        self._refresh_worker: StateWorker | None = None
        self._action_thread: QThread | None = None
        self._action_worker = None

        self._busy = False
        self._busy_text = ''
        self._tests_running = False
        self._pending_toggle: bool | None = None
        self._settle_deadline = 0.0
        self._settle_ok = False
        self._settle_msg = ''

        self._post_waiting = False
        self._post_deadline = 0.0
        self._post_title = ''
        self._post_msg = ''
        self._post_notify = False

        self._bg_src = None
        self._bg_pm = None
        self._bg_x = 0
        self._bg_y = 0

        build_service_tab(self)
        self._wire()
        init_background(self)

        if initial_state:
            self._selected_strategy = (initial_state.selected_strategy or '').strip()
            apply_state(self, initial_state)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(2000)
        QTimer.singleShot(0, self.refresh)

    def _wire(self) -> None:
        self.swEnabled.toggled.connect(self._toggle_requested)
        self.combo.currentTextChanged.connect(self._strategy_changed)
        self.combo.activated.connect(self._strategy_activated)
        self.btnInstallZapret.clicked.connect(self._install_zapret)
        self.btnApplyStrategy.clicked.connect(self._apply_strategy)
        self.btnRemove.clicked.connect(self._remove_services)
        self.btnRemoveGoodbye.clicked.connect(self._remove_goodbye)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        update_background(self)
        update_strategy_width(self)

    def paintEvent(self, event):
        super().paintEvent(event)
        paint_background(self)

    def _update_strategy_width(self) -> None:
        update_strategy_width(self)

    def toggle(self) -> None:
        if self._tests_running or (not self._state):
            return
        self._toggle_requested(not self._state.enabled)

    def install_zapret(self) -> None:
        if self._busy or self._tests_running:
            return
        self._install_zapret()

    def apply_strategy_from_tray(self, strategy: str) -> None:
        if self._busy or self._tests_running:
            return
        value = (strategy or '').strip()
        if not value:
            return
        if self.combo.isVisible():
            set_combo_value(self.combo, value)
            self._strategy_changed(self.combo.currentText())
        self._apply_strategy()

    def set_tests_running(self, running: bool) -> None:
        self._tests_running = bool(running)
        if self._state and (not self._busy):
            apply_state(self, self._state)
        else:
            emit_tray_state(self)

    def get_tray_model(self) -> dict:
        state = self._state
        if not state:
            return {'ready': False}
        return {
            'ready': True,
            'busy': bool(self._busy),
            'tests_running': bool(self._tests_running),
            'show_install_zapret': bool(state.show_install_zapret),
            'show_strategy_select': bool(state.show_strategy_select),
            'external_present': bool(state.external_present),
            'enabled': bool(state.enabled),
            'current_strategy': (state.current_strategy or '').strip(),
            'selected_strategy': (self._selected_strategy or state.selected_strategy or '').strip(),
            'strategies': list(state.strategies or []),
        }

    def get_enabled(self) -> bool:
        return bool(self._state.enabled) if self._state else False

    def refresh(self) -> None:
        if self._refresh_thread:
            return
        self._refresh_thread = QThread()
        self._refresh_worker = StateWorker(lambda: self.ctrl.build_state(self._selected_strategy))
        self._refresh_worker.moveToThread(self._refresh_thread)
        self._refresh_thread.started.connect(self._refresh_worker.run)
        self._refresh_worker.done.connect(self._on_refresh_done)
        self._refresh_worker.error.connect(self._on_refresh_error)
        self._refresh_thread.start()

    def _on_refresh_done(self, state: HomeState) -> None:
        try:
            if self._busy and self._pending_toggle is not None:
                handle_settle_state(self, state)
            elif self._busy and self._post_waiting:
                handle_post_state(self, state)
            elif not self._busy:
                apply_state(self, state)
        finally:
            self._cleanup_refresh_worker()

    def _on_refresh_error(self, msg: str) -> None:
        try:
            if not self._busy:
                self._state = None
                QMessageBox.critical(self, 'Обновление статуса', msg or 'Ошибка')
        finally:
            self._cleanup_refresh_worker()

    def _cleanup_refresh_worker(self) -> None:
        if self._refresh_thread:
            self._refresh_thread.quit()
            self._refresh_thread.wait(2000)
        self._refresh_thread = None
        self._refresh_worker = None

    def _strategy_changed(self, value: str) -> None:
        if self.combo.hasFocus():
            self._user_picked_strategy = True
        self._selected_strategy = (value or '').strip()
        self.cfg.last_strategy = self._selected_strategy
        self.cfg.save()
        from src.ui.tabs.service_tab_state import update_apply_button
        update_apply_button(self, self.combo.isEnabled() and (not self._busy) and (not self._tests_running))
        emit_tray_state(self)

    def _strategy_activated(self, _index: int) -> None:
        self._user_picked_strategy = True

    def _toggle_requested(self, on: bool) -> None:
        toggle_requested(self, on)

    def _install_zapret(self) -> None:
        install_zapret(self)

    def _apply_strategy(self) -> None:
        apply_strategy(self)

    def _remove_services(self) -> None:
        remove_services(self)

    def _remove_goodbye(self) -> None:
        remove_goodbye(self)

    def _run_action(self, fn, title: str, success_notify: bool = False) -> None:
        run_action(self, fn, title, success_notify)

    def _on_action_done(self, ok: bool, msg: str, title: str, success_notify: bool) -> None:
        on_action_done(self, ok, msg, title, success_notify)
