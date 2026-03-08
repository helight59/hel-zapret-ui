from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from src.app.config import AppConfig
from src.services.zapret.user_lists import read_existing_user_lists, sync_saved_user_lists
from src.ui.components import BusyStrip, Card, TOKENS
from src.ui.tabs.settings_lists_runtime import clear_runtime_worker, finish_restart, refresh_runtime_state_async, restart_now, service_sync_timeout
from src.ui.tabs.settings_lists_widgets import EditableListCard, make_padded_icon
from src.utils.paths import bundle_dir


class SettingsListsTab(QWidget):
    appStatusChanged = Signal(str)
    globalBusyChanged = Signal(bool)
    serviceSyncRequested = Signal()

    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg

        self._busy = False
        self._runtime_enabled = False
        self._last_status_text = ''
        self._last_error = ''
        self._pending_runtime_refresh = False
        self._post_restart_sync = False
        self._finish_after_runtime_refresh = False
        self._restart_thread: QThread | None = None
        self._restart_worker = None
        self._runtime_thread: QThread | None = None
        self._runtime_worker = None

        delete_icon = bundle_dir() / 'assets' / 'icons' / 'delete.png'
        add_icon = bundle_dir() / 'assets' / 'icons' / 'plus.png'
        self._delete_icon = make_padded_icon(delete_icon, padding=3)
        self._add_icon = make_padded_icon(add_icon, padding=2)

        self._build()
        self._wire()
        self._load_from_config()
        refresh_runtime_state_async(self)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.busyStrip = BusyStrip()
        outer.addWidget(self.busyStrip)

        body = QWidget()
        layout = QHBoxLayout(body)
        layout.setContentsMargins(0, 0, TOKENS.space_xl, TOKENS.space_xl)
        layout.setSpacing(TOKENS.space_m)

        self.contentScroll = QScrollArea()
        self.contentScroll.setFrameShape(QFrame.NoFrame)
        self.contentScroll.setWidgetResizable(True)
        self.contentScroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.contentScroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.contentScroll.viewport().setAutoFillBackground(False)

        self.contentWidget = QWidget()
        self.contentLayout = QVBoxLayout(self.contentWidget)
        self.contentLayout.setContentsMargins(TOKENS.space_xl, TOKENS.space_xl, TOKENS.space_xl, TOKENS.space_m)
        self.contentLayout.setSpacing(TOKENS.space_l)

        self.cardForward = EditableListCard(
            'Сайты для обхода',
            'Добавь сюда сайты, которым стоит помочь открываться стабильнее.',
            'Добавить сайт для обхода',
            'Укажи сайт, который нужно добавить в список. Например: discord.com или youtube.com.',
            'example.com',
            self._delete_icon,
            self._add_icon,
        )
        self.cardBypassOff = EditableListCard(
            'Сайты без изменений',
            'Если какой-то сайт и так работает хорошо, можно оставить его в покое.',
            'Добавить сайт без изменений',
            'Укажи сайт, который zapret не должен трогать. Например: vk.com или habr.com.',
            'example.com',
            self._delete_icon,
            self._add_icon,
        )
        self.cardIpExclude = EditableListCard(
            'Адреса без изменений',
            'Отдельные адреса сети, которые лучше не трогать вообще.',
            'Добавить адрес без изменений',
            'Укажи IP или подсеть. Например: 203.0.113.10/32 или 192.168.0.0/16.',
            '203.0.113.10/32',
            self._delete_icon,
            self._add_icon,
        )

        self._sections = [
            ('forward', self.cardForward),
            ('exclude', self.cardBypassOff),
            ('ips', self.cardIpExclude),
        ]
        for _key, card in self._sections:
            self.contentLayout.addWidget(card)
        self.contentLayout.addSpacing(10)
        self.contentLayout.addStretch(1)

        self.contentScroll.setWidget(self.contentWidget)
        layout.addWidget(self.contentScroll, 1)

        self.navWrap = QWidget()
        self.navWrapLayout = QVBoxLayout(self.navWrap)
        self.navWrapLayout.setContentsMargins(TOKENS.space_m, TOKENS.space_xl, TOKENS.space_m, TOKENS.space_l)
        self.navWrapLayout.setSpacing(0)

        self.navCard = Card('Списки')
        self.navCard.setFixedWidth(220)
        self.navWrapLayout.addWidget(self.navCard)
        nav = self.navCard.body

        self.lblNavHelp = QLabel('Быстрый переход по разделам и применение изменений.')
        self.lblNavHelp.setWordWrap(True)
        self.lblNavHelp.setProperty('muted', True)
        nav.addWidget(self.lblNavHelp)

        self.btnNavForward = QPushButton('Сайты для обхода')
        self.btnNavForward.setProperty('anchorBtn', True)
        nav.addWidget(self.btnNavForward)
        self.btnNavBypassOff = QPushButton('Сайты без изменений')
        self.btnNavBypassOff.setProperty('anchorBtn', True)
        nav.addWidget(self.btnNavBypassOff)
        self.btnNavIps = QPushButton('Адреса без изменений')
        self.btnNavIps.setProperty('anchorBtn', True)
        nav.addWidget(self.btnNavIps)

        self.lblStatus = QLabel('')
        self.lblStatus.setWordWrap(True)
        self.lblStatus.setProperty('muted', True)
        nav.addWidget(self.lblStatus)

        self.btnApply = QPushButton('Применить')
        self.btnApply.setVisible(False)
        nav.addWidget(self.btnApply)
        nav.addStretch(1)

        layout.addWidget(self.navWrap, 0, Qt.AlignTop)
        outer.addWidget(body, 1)

    def _wire(self) -> None:
        self.cardForward.changed.connect(self._on_lists_changed)
        self.cardBypassOff.changed.connect(self._on_lists_changed)
        self.cardIpExclude.changed.connect(self._on_lists_changed)
        self.btnApply.clicked.connect(self._apply_changes)
        self.btnNavForward.clicked.connect(lambda: self._scroll_to_section(self.cardForward))
        self.btnNavBypassOff.clicked.connect(lambda: self._scroll_to_section(self.cardBypassOff))
        self.btnNavIps.clicked.connect(lambda: self._scroll_to_section(self.cardIpExclude))

    def _load_from_config(self) -> None:
        self.cardForward.set_entries(self.cfg.custom_forward_domains)
        self.cardBypassOff.set_entries(self.cfg.custom_blocked_domains)
        self.cardIpExclude.set_entries(self.cfg.custom_excluded_ips)
        self._sync_ui(applied_to_zapret=None)
        QTimer.singleShot(0, self._update_anchor_state)

    def _state_from_cards(self) -> dict[str, list[str]]:
        return {
            'custom_forward_domains': self.cardForward.entries(),
            'custom_blocked_domains': self.cardBypassOff.entries(),
            'custom_excluded_ips': self.cardIpExclude.entries(),
        }

    def _zapret_ready(self) -> bool:
        return (Path(self.cfg.zapret_dir) / 'bin' / 'winws.exe').exists()

    def _read_applied_state(self) -> dict[str, list[str]] | None:
        if not self._zapret_ready():
            return None
        try:
            return read_existing_user_lists(Path(self.cfg.zapret_dir))
        except Exception:
            return None

    def _files_need_apply(self) -> bool:
        if not self._zapret_ready():
            return False
        applied_state = self._read_applied_state()
        if applied_state is None:
            return True
        return self._state_from_cards() != applied_state

    def _needs_apply(self) -> bool:
        return self._zapret_ready() and self._files_need_apply()

    def _persist_cards_to_config(self) -> bool:
        state = self._state_from_cards()
        try:
            self.cfg.custom_forward_domains = state['custom_forward_domains']
            self.cfg.custom_blocked_domains = state['custom_blocked_domains']
            self.cfg.custom_excluded_ips = state['custom_excluded_ips']
            self.cfg.save()
            return True
        except Exception:
            self._last_error = 'Не получилось сохранить списки в настройках приложения.'
            return False

    def _on_lists_changed(self) -> None:
        self._last_error = ''
        if self._persist_cards_to_config():
            self._last_status_text = 'Списки сохранены в приложении.'
        self._sync_ui(applied_to_zapret=None)

    def _set_busy(self, value: bool, text: str) -> None:
        self._busy = bool(value)
        self.busyStrip.set_busy(self._busy)
        for _key, card in self._sections:
            card.setEnabled(not self._busy)
        self.btnApply.setEnabled((not self._busy) and self._needs_apply())
        self.globalBusyChanged.emit(self._busy)
        self.appStatusChanged.emit((text or '').strip() if self._busy else '')

    def _sync_ui(self, applied_to_zapret: bool | None) -> None:
        needs_apply = self._needs_apply()
        zapret_ready = self._zapret_ready()
        self.btnApply.setVisible(needs_apply)
        self.btnApply.setText('Применить и перезапустить' if self._runtime_enabled else 'Применить')
        self.btnApply.setEnabled((not self._busy) and needs_apply)

        if self._last_error:
            text = self._last_error
        elif not zapret_ready:
            text = 'Списки уже сохранены в приложении. Они автоматически подставятся после установки или обновления zapret.'
        elif applied_to_zapret is False:
            text = 'Списки сохранены в приложении, но сейчас не удалось записать их в файлы zapret.'
        elif needs_apply and self._runtime_enabled:
            text = 'Списки уже сохранены. Нажми «Применить и перезапустить», чтобы сразу обновить работающий zapret.'
        elif needs_apply:
            text = 'Списки уже сохранены. Нажми «Применить», чтобы записать их в zapret.'
        elif self._last_status_text:
            text = self._last_status_text
        else:
            text = 'Списки уже сохранены и применены.'
        self.lblStatus.setText(text)

    def _apply_changes(self) -> None:
        if self._busy or not self._needs_apply():
            return
        applied = sync_saved_user_lists(Path(self.cfg.zapret_dir), Path(self.cfg.data_dir))
        if applied is False:
            self._last_error = 'Не получилось сразу записать списки в файлы zapret. Но они уже сохранены в приложении.'
            self._last_status_text = ''
            self._sync_ui(applied_to_zapret=False)
            return
        self._last_error = ''
        if self._runtime_enabled:
            self._last_status_text = 'Списки записаны. Перезапускаем zapret, чтобы применить их сразу.'
            restart_now(self)
            return
        self._last_status_text = 'Списки применены. Новые значения уже используются.'
        self._sync_ui(applied_to_zapret=True)

    def _refresh_runtime_state_async(self) -> None:
        refresh_runtime_state_async(self)

    def _on_runtime_refresh_done(self, snapshot: object) -> None:
        try:
            data = snapshot if isinstance(snapshot, dict) else {}
            self._runtime_enabled = bool(data.get('enabled'))
            self._sync_ui(applied_to_zapret=None)
            if self._finish_after_runtime_refresh:
                self._finish_after_runtime_refresh = False
                self._last_error = ''
                self._last_status_text = 'Списки применены. Новые значения уже используются.'
                self._set_busy(False, '')
                self._sync_ui(applied_to_zapret=None)
        finally:
            clear_runtime_worker(self)
            if self._pending_runtime_refresh:
                self._pending_runtime_refresh = False
                refresh_runtime_state_async(self)

    def _on_runtime_refresh_error(self, _msg: str) -> None:
        try:
            self._runtime_enabled = False
            self._sync_ui(applied_to_zapret=None)
            if self._finish_after_runtime_refresh:
                self._finish_after_runtime_refresh = False
                self._last_status_text = 'Списки сохранены. Текущее состояние zapret обновить не удалось.'
                self._set_busy(False, '')
                self._sync_ui(applied_to_zapret=None)
        finally:
            clear_runtime_worker(self)
            if self._pending_runtime_refresh:
                self._pending_runtime_refresh = False
                refresh_runtime_state_async(self)

    def _restart_now(self) -> None:
        restart_now(self)

    def _on_restart_done(self, ok: bool, msg: str) -> None:
        finish_restart(self, ok, msg)

    def _service_sync_timeout(self) -> None:
        service_sync_timeout(self)

    def on_service_sync_finished(self) -> None:
        if not self._post_restart_sync:
            self._sync_ui(applied_to_zapret=None)
            refresh_runtime_state_async(self)
            return
        self._post_restart_sync = False
        self._finish_after_runtime_refresh = True
        self.appStatusChanged.emit('Проверяем статус...')
        refresh_runtime_state_async(self)

    def refresh_state(self) -> None:
        self._sync_ui(applied_to_zapret=None)
        refresh_runtime_state_async(self)

    def _scroll_to_section(self, section: QWidget) -> None:
        bar = self.contentScroll.verticalScrollBar()
        target = min(max(0, section.y()), bar.maximum())
        bar.setValue(target)

    def _update_anchor_state(self) -> None:
        self.btnNavForward.setChecked(False)
        self.btnNavBypassOff.setChecked(False)
        self.btnNavIps.setChecked(False)
