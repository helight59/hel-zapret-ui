from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QStackedWidget, QVBoxLayout, QWidget

from src.app.config import AppConfig
from src.ui.tabs.settings_lists_tab import SettingsListsTab
from src.ui.tabs.settings_tab import SettingsTab
from src.ui.tabs.settings_zapret_tab import ZapretSettingsTab
from src.ui.components import TOKENS


class SettingsContainerTab(QWidget):
    routeSelected = Signal(str)
    zapretVersionChanged = Signal(str)
    appStatusChanged = Signal(str)
    globalBusyChanged = Signal(bool)
    serviceSyncRequested = Signal()
    runtimeRefreshBusyChanged = Signal(bool)

    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg

        self.settings_app_tab = SettingsTab(cfg)
        self.settings_app_tab.zapretVersionChanged.connect(self.zapretVersionChanged)
        self.settings_zapret_tab = ZapretSettingsTab(cfg)
        self.settings_zapret_tab.appStatusChanged.connect(self.appStatusChanged)
        self.settings_zapret_tab.globalBusyChanged.connect(self.globalBusyChanged)
        self.settings_zapret_tab.serviceSyncRequested.connect(self.serviceSyncRequested)
        self.settings_zapret_tab.runtimeRefreshBusyChanged.connect(self.runtimeRefreshBusyChanged)
        self.settings_lists_tab = SettingsListsTab(cfg)
        self.settings_lists_tab.appStatusChanged.connect(self.appStatusChanged)
        self.settings_lists_tab.globalBusyChanged.connect(self.globalBusyChanged)
        self.settings_lists_tab.serviceSyncRequested.connect(self.serviceSyncRequested)

        self._route = 'settings_app'
        self._build()
        self._wire()
        self.set_route('settings_app')

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(TOKENS.space_m)

        bar = QFrame()
        bar.setProperty('subMenuBar', True)
        row = QHBoxLayout(bar)
        row.setContentsMargins(TOKENS.space_l, TOKENS.space_m - 2, TOKENS.space_l, TOKENS.space_m - 2)
        row.setSpacing(TOKENS.space_m)

        title = QLabel('Настройки')
        title.setProperty('pageTitle', True)
        row.addWidget(title)
        row.addStretch(1)

        self.btnApp = QPushButton('Приложение')
        self.btnApp.setCursor(Qt.PointingHandCursor)
        self.btnApp.setCheckable(True)
        self.btnApp.setProperty('subTopBtn', True)
        row.addWidget(self.btnApp)

        self.btnZapret = QPushButton('Zapret')
        self.btnZapret.setCursor(Qt.PointingHandCursor)
        self.btnZapret.setCheckable(True)
        self.btnZapret.setProperty('subTopBtn', True)
        row.addWidget(self.btnZapret)

        self.btnLists = QPushButton('Списки')
        self.btnLists.setCursor(Qt.PointingHandCursor)
        self.btnLists.setCheckable(True)
        self.btnLists.setProperty('subTopBtn', True)
        row.addWidget(self.btnLists)

        wrap = QWidget()
        w = QVBoxLayout(wrap)
        w.setContentsMargins(TOKENS.space_xl, TOKENS.space_xl, TOKENS.space_xl, 0)
        w.setSpacing(0)
        w.addWidget(bar)
        root.addWidget(wrap, 0)

        self.pages = QStackedWidget()
        self.pages.addWidget(self._wrap_page(self.settings_app_tab))
        self.pages.addWidget(self._wrap_page(self.settings_zapret_tab))
        self.pages.addWidget(self.settings_lists_tab)
        root.addWidget(self.pages, 1)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._group.addButton(self.btnApp)
        self._group.addButton(self.btnZapret)
        self._group.addButton(self.btnLists)

    def _wire(self) -> None:
        self.btnApp.clicked.connect(lambda: self.routeSelected.emit('settings_app'))
        self.btnZapret.clicked.connect(lambda: self.routeSelected.emit('settings_zapret'))
        self.btnLists.clicked.connect(lambda: self.routeSelected.emit('settings_lists'))

    def _wrap_page(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(widget)
        return scroll

    def set_route(self, route: str) -> None:
        r = (route or '').strip() or 'settings_app'
        if r not in ('settings_app', 'settings_zapret', 'settings_lists'):
            r = 'settings_app'
        self._route = r

        if r == 'settings_app':
            self.btnApp.setChecked(True)
            self.pages.setCurrentIndex(0)
            return

        if r == 'settings_zapret':
            self.btnZapret.setChecked(True)
            self.pages.setCurrentIndex(1)
            self.settings_zapret_tab.refresh_state()
            return

        self.btnLists.setChecked(True)
        self.pages.setCurrentIndex(2)
        self.settings_lists_tab.refresh_state()

    def set_global_busy(self, busy: bool) -> None:
        locked = bool(busy)
        self.btnApp.setEnabled(not locked)
        self.btnZapret.setEnabled(not locked)
        self.btnLists.setEnabled(not locked)
        self.settings_app_tab.setEnabled(not locked)

    def on_service_sync_finished(self) -> None:
        self.settings_zapret_tab.on_service_sync_finished()
        self.settings_lists_tab.on_service_sync_finished()

    def on_service_state_refreshed(self) -> None:
        if self._route == 'settings_zapret':
            self.settings_zapret_tab.refresh_state()
            return
        if self._route == 'settings_lists':
            self.settings_lists_tab.refresh_state()
