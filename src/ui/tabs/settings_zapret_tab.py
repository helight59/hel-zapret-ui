from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import time

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.app.config import AppConfig
from src.services.zapret.game_filter import GAME_FILTER_ALL, GAME_FILTER_DISABLED, GAME_FILTER_TCP, GAME_FILTER_UDP, GAME_FILTER_UNKNOWN, clear_runtime_game_filter_override, game_filter_available, is_known_game_filter_mode, set_runtime_game_filter_override, write_game_filter_mode
from src.services.zapret.game_filter_state import GameFilterState, read_game_filter_state
from src.services.zapret.game_filter_ui_state import clear_game_filter_editor_dirty, make_game_filter_editor_state, set_game_filter_editor_dirty_mode, sync_game_filter_editor_dirty
from src.services.zapret.service import ZapretService
from src.ui.adapters.fn_worker import FnWorker
from src.ui.adapters.state_worker import StateWorker
from src.ui.components import BusyStrip, Card, TOKENS


class ZapretSettingsTab(QWidget):
    appStatusChanged = Signal(str)
    globalBusyChanged = Signal(bool)
    serviceSyncRequested = Signal()
    runtimeRefreshBusyChanged = Signal(bool)

    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg

        self._loading = False
        self._busy = False
        self._busy_text = ''
        self._runtime_enabled = False
        self._runtime_mode = GAME_FILTER_DISABLED
        self._runtime_loaded = False
        self._game_filter_state = GameFilterState(
            available=False,
            enabled=False,
            desired_mode=GAME_FILTER_DISABLED,
            runtime_mode=GAME_FILTER_DISABLED,
            effective_runtime_mode=GAME_FILTER_DISABLED,
            runtime_mode_known=True,
            restart_required=False,
        )
        self._restart_thread: QThread | None = None
        self._restart_worker: FnWorker | None = None
        self._runtime_thread: QThread | None = None
        self._runtime_worker: StateWorker | None = None
        self._pending_runtime_refresh = False
        self._post_restart_sync = False
        self._finish_after_runtime_refresh = False
        self._restart_verify_deadline = 0.0
        self._restart_target_mode = GAME_FILTER_DISABLED
        self._restart_verifying = False

        self._build()
        self._wire()
        self._reload_from_state()

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.busyStrip = BusyStrip()
        outer.addWidget(self.busyStrip)

        content = QWidget()
        outer.addWidget(content, 1)

        root = QVBoxLayout(content)
        root.setContentsMargins(TOKENS.space_xl, TOKENS.space_xl, TOKENS.space_xl, TOKENS.space_xl)
        root.setSpacing(TOKENS.space_l)

        self.cardGame = Card('Игровой режим')
        gv = self.cardGame.body

        self.lblIntro = QLabel(
            'Полезно, если игра долго подключается, не пускает в матч, ломает голосовой чат '
            'или иногда теряет соединение. Проще говоря: zapret будет активнее помогать именно играм.'
        )
        self.lblIntro.setWordWrap(True)
        gv.addWidget(self.lblIntro)

        self.chkEnabled = QCheckBox('Включить игровой режим')
        gv.addWidget(self.chkEnabled)

        mode_row = QHBoxLayout()
        mode_row.setSpacing(TOKENS.space_m)
        mode_row.addWidget(QLabel('Как применять'))
        self.cmbMode = QComboBox()
        self.cmbMode.setMinimumWidth(280)
        self.cmbMode.addItem('Для большинства игр', GAME_FILTER_ALL)
        self.cmbMode.addItem('Бережно: только UDP', GAME_FILTER_UDP)
        self.cmbMode.addItem('Только TCP', GAME_FILTER_TCP)
        mode_row.addWidget(self.cmbMode)
        mode_row.addStretch(1)
        gv.addLayout(mode_row)

        actions_row = QHBoxLayout()
        actions_row.setSpacing(TOKENS.space_m)
        self.lblRestartHint = QLabel('')
        self.lblRestartHint.setWordWrap(True)
        self.lblRestartHint.setProperty('muted', True)
        actions_row.addWidget(self.lblRestartHint, 1)
        self.btnRestart = QPushButton('Сохранить')
        self.btnRestart.setProperty('variant', 'secondary')
        self.btnRestart.setFocusPolicy(Qt.NoFocus)
        self.btnRestart.setVisible(False)
        actions_row.addWidget(self.btnRestart)
        gv.addLayout(actions_row)

        self.cardHelp = Card('Когда это полезно')
        hv = self.cardHelp.body
        self.lblHelp = QLabel(
            'Включай, если проблема именно в играх: долго ищется матч, не заходит в лобби, '
            'плохо работает голосовой чат или игра видит интернет через раз. Если всё и так '
            'нормально и тебе нужны только сайты, YouTube или Discord, можно оставить выключенным.'
        )
        self.lblHelp.setWordWrap(True)
        self.lblHelp.setProperty('muted', True)
        hv.addWidget(self.lblHelp)

        root.addWidget(self.cardGame)
        root.addWidget(self.cardHelp)
        root.addStretch(1)

    def _wire(self) -> None:
        self.chkEnabled.toggled.connect(self._queue_save_from_ui)
        self.cmbMode.currentIndexChanged.connect(self._queue_save_from_ui)
        self.btnRestart.clicked.connect(self._apply_changes)

    def _reload_from_state(self) -> None:
        self._loading = True
        try:
            self.chkEnabled.setChecked(False)
            self._select_mode(GAME_FILTER_ALL)
            self._sync_ui()
        finally:
            self._loading = False
        self._refresh_runtime_state_async()

    def _selected_mode(self) -> str:
        if not self.chkEnabled.isChecked():
            return GAME_FILTER_DISABLED
        return str(self.cmbMode.currentData() or GAME_FILTER_ALL)

    def _queue_save_from_ui(self) -> None:
        if self._loading or self._busy:
            return

        self._apply_editor_choice(self._selected_mode())
        self._sync_ui()

    def _apply_editor_choice(self, new_mode: str) -> None:
        editor_state = make_game_filter_editor_state(self._game_filter_state, self.cfg)
        compare_mode = editor_state.service_mode if self._game_filter_state.enabled else editor_state.desired_mode
        if new_mode == compare_mode:
            clear_game_filter_editor_dirty(self.cfg)
            return
        set_game_filter_editor_dirty_mode(self.cfg, new_mode)

    def _save_selected_mode(self, new_mode: str) -> None:
        self.cfg.game_filter_mode = new_mode
        self.cfg.save()
        if game_filter_available(Path(self.cfg.zapret_dir)):
            write_game_filter_mode(Path(self.cfg.zapret_dir), new_mode)

    def _apply_changes(self) -> None:
        if self._busy:
            return

        new_mode = self._selected_mode()
        self._save_selected_mode(new_mode)

        if not self._game_filter_state.enabled:
            clear_game_filter_editor_dirty(self.cfg)
            self._game_filter_state = replace(self._game_filter_state, desired_mode=new_mode, restart_required=False)
            self._sync_ui()
            return

        self._restart_now()

    def _read_runtime_snapshot(self) -> GameFilterState:
        return read_game_filter_state(self.cfg.zapret_dir, self.cfg.data_dir, self.cfg)

    def _refresh_runtime_state_async(self) -> None:
        if self._runtime_thread:
            self._pending_runtime_refresh = True
            return
        self._runtime_thread = QThread()
        self._runtime_worker = StateWorker(self._read_runtime_snapshot)
        self._runtime_worker.moveToThread(self._runtime_thread)
        self._runtime_thread.started.connect(self._runtime_worker.run)
        self._runtime_worker.done.connect(self._on_runtime_refresh_done)
        self._runtime_worker.error.connect(self._on_runtime_refresh_error)
        self._runtime_thread.start()

    def _on_runtime_refresh_done(self, snapshot: object) -> None:
        try:
            state = snapshot if isinstance(snapshot, GameFilterState) else GameFilterState(
                available=False,
                enabled=False,
                desired_mode=GAME_FILTER_DISABLED,
                runtime_mode=GAME_FILTER_DISABLED,
                effective_runtime_mode=GAME_FILTER_DISABLED,
                runtime_mode_known=True,
                restart_required=False,
            )
            self._game_filter_state = state
            sync_game_filter_editor_dirty(self.cfg, state)
            self._game_filter_state = state
            self._runtime_enabled = bool(state.enabled)
            self._runtime_mode = str(state.runtime_mode or GAME_FILTER_UNKNOWN)
            self._runtime_loaded = True
            if not self._runtime_enabled:
                clear_runtime_game_filter_override(self.cfg)
            self._sync_ui()
            if self._restart_verifying:
                self._handle_restart_verification()
            elif self._finish_after_runtime_refresh:
                self._finish_after_runtime_refresh = False
                self._set_busy(False, '')
                self._sync_ui()
        finally:
            self._clear_runtime_worker()
            if self._pending_runtime_refresh:
                self._pending_runtime_refresh = False
                self._refresh_runtime_state_async()

    def _on_runtime_refresh_error(self, _msg: str) -> None:
        try:
            self._game_filter_state = GameFilterState(
                available=False,
                enabled=False,
                desired_mode=str(getattr(self.cfg, 'game_filter_mode', GAME_FILTER_DISABLED) or GAME_FILTER_DISABLED),
                runtime_mode=GAME_FILTER_DISABLED,
                effective_runtime_mode=GAME_FILTER_DISABLED,
                runtime_mode_known=True,
                restart_required=False,
            )
            self._runtime_enabled = False
            self._runtime_mode = GAME_FILTER_DISABLED
            self._runtime_loaded = False
            clear_runtime_game_filter_override(self.cfg)
            self._sync_ui()
            if self._restart_verifying:
                self._handle_restart_verification()
            elif self._finish_after_runtime_refresh:
                self._finish_after_runtime_refresh = False
                self._set_busy(False, '')
                self._sync_ui()
        finally:
            self._clear_runtime_worker()
            if self._pending_runtime_refresh:
                self._pending_runtime_refresh = False
                self._refresh_runtime_state_async()

    def _clear_runtime_worker(self) -> None:
        if self._runtime_thread:
            self._runtime_thread.quit()
            self._runtime_thread.wait(2000)
        self._runtime_thread = None
        self._runtime_worker = None

    def _set_busy(self, v: bool, text: str) -> None:
        self._busy = bool(v)
        self._busy_text = (text or '').strip()
        self.globalBusyChanged.emit(self._busy)
        self._render_busy_state()

    def _render_busy_state(self) -> None:
        self.busyStrip.set_busy(self._busy)
        self.chkEnabled.setEnabled(not self._busy)
        self.cmbMode.setEnabled(self.chkEnabled.isChecked() and (not self._busy))
        self.btnRestart.setEnabled(not self._busy)
        self.appStatusChanged.emit(self._busy_text if self._busy else '')

    def _sync_ui(self) -> None:
        state = self._game_filter_state
        editor_state = make_game_filter_editor_state(state, self.cfg)
        pending_mode = editor_state.ui_mode
        compare_mode = editor_state.service_mode if state.enabled else editor_state.desired_mode

        self._loading = True
        try:
            self.chkEnabled.setChecked(editor_state.ui_enabled)
            if editor_state.ui_enabled:
                self._select_mode(editor_state.ui_mode)
        finally:
            self._loading = False

        self.chkEnabled.setEnabled(not self._busy)
        self.cmbMode.setEnabled(self.chkEnabled.isChecked() and (not self._busy))

        show_apply = (not self._busy) and state.available and (pending_mode != compare_mode)
        self.btnRestart.setVisible(show_apply)
        self.lblRestartHint.setVisible(show_apply)
        if not show_apply:
            self.btnRestart.setText('Сохранить и перезапустить' if state.enabled else 'Сохранить')
            self.lblRestartHint.setText('')
            return

        if state.enabled:
            self.btnRestart.setText('Сохранить и перезапустить')
            self.lblRestartHint.setText('Игровой режим в настройках отличается от текущего запущенного режима. Сохрани изменение и перезапусти zapret.')
            return

        self.btnRestart.setText('Сохранить')
        self.lblRestartHint.setText('Zapret сейчас не запущен. Сохрани настройку, и она применится при следующем запуске.')

    def _select_mode(self, mode: str) -> None:
        value = (mode or '').strip().lower()
        for i in range(self.cmbMode.count()):
            if str(self.cmbMode.itemData(i) or '') == value:
                self.cmbMode.setCurrentIndex(i)
                return
        self.cmbMode.setCurrentIndex(0)

    def _restart_now(self) -> None:
        if self._busy or self._restart_thread or (not self._runtime_enabled):
            return

        desired_mode = self._selected_mode()
        self._restart_thread = QThread()
        svc = ZapretService(Path(self.cfg.zapret_dir), Path(self.cfg.data_dir))
        self._restart_worker = FnWorker(lambda: svc.restart(self.cfg.last_strategy or ''))
        self._restart_worker.moveToThread(self._restart_thread)
        self._restart_thread.started.connect(self._restart_worker.run)
        self._restart_worker.done.connect(self._on_restart_done)
        self._restart_target_mode = desired_mode
        self._restart_verify_deadline = 0.0
        self._restart_verifying = False
        self._restart_thread.start()
        self._set_busy(True, 'Перезапускаем zapret...')
        self._sync_ui()

    def _on_restart_done(self, ok: bool, msg: str) -> None:
        if self._restart_thread:
            self._restart_thread.quit()
            self._restart_thread.wait(2000)
        self._restart_thread = None
        self._restart_worker = None

        if not ok:
            self._refresh_runtime_state_async()
            self._set_busy(False, '')
            self._sync_ui()
            return

        self._post_restart_sync = True
        self._restart_target_mode = self._selected_mode()
        set_runtime_game_filter_override(self.cfg, self._restart_target_mode)
        self._restart_verify_deadline = time.monotonic() + 20.0
        self._restart_verifying = True
        self.appStatusChanged.emit('Проверяем статус...')
        self.serviceSyncRequested.emit()
        QTimer.singleShot(1500, self._service_sync_timeout)

    def _service_sync_timeout(self) -> None:
        if not self._post_restart_sync:
            return
        self.on_service_sync_finished()

    def refresh_state(self) -> None:
        self._refresh_runtime_state_async()

    def on_service_sync_finished(self) -> None:
        if not self._post_restart_sync:
            self._sync_ui()
            self._refresh_runtime_state_async()
            return
        self._post_restart_sync = False
        self.appStatusChanged.emit('Проверяем запущенный режим...')
        self._refresh_runtime_state_async()

    def _handle_restart_verification(self) -> None:
        target_mode = (self._restart_target_mode or self._selected_mode() or GAME_FILTER_DISABLED).strip().lower()
        runtime_mode = (self._runtime_mode or GAME_FILTER_UNKNOWN).strip().lower()
        runtime_known = is_known_game_filter_mode(runtime_mode)

        if self._runtime_enabled and runtime_known and runtime_mode == target_mode:
            self._restart_verifying = False
            set_runtime_game_filter_override(self.cfg, target_mode)
            self._set_busy(False, '')
            self._sync_ui()
            self.serviceSyncRequested.emit()
            return

        if time.monotonic() < self._restart_verify_deadline:
            self.appStatusChanged.emit('Ждём запуск с новым игровым режимом...')
            self.serviceSyncRequested.emit()
            QTimer.singleShot(1200, self._refresh_runtime_state_async)
            return

        self._restart_verifying = False
        if self._runtime_enabled:
            set_runtime_game_filter_override(self.cfg, target_mode)
        self._set_busy(False, '')
        self._sync_ui()
        self.serviceSyncRequested.emit()
