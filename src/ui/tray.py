from __future__ import annotations

import logging
from functools import partial

from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from src.utils.icon import app_icon
from src.services.zapret.strategy_name import normalize_strategy_key


log = logging.getLogger('ui.tray')


class TrayController(QObject):
    toggleRequested = Signal()
    installRequested = Signal()
    showRequested = Signal()
    exitRequested = Signal()
    applyStrategyRequested = Signal(str)

    def __init__(self):
        super().__init__()
        self.tray = QSystemTrayIcon(app_icon())
        self.menu = QMenu()

        self.actToggle = QAction('Включить')
        self.actToggle.triggered.connect(self.toggleRequested.emit)

        self.actInstall = QAction('Установить')
        self.actInstall.triggered.connect(self.installRequested.emit)

        self.actOpen = QAction('Открыть')
        self.actOpen.triggered.connect(self.showRequested.emit)

        self.menuStrategies = QMenu('Смена стратегии')

        self.actExit = QAction('Выход')
        self.actExit.triggered.connect(self.exitRequested.emit)

        self.menu.addAction(self.actToggle)
        self.menu.addAction(self.actInstall)
        self.menu.addSeparator()
        self.menu.addAction(self.actOpen)
        self.menu.addMenu(self.menuStrategies)
        self.menu.addSeparator()
        self.menu.addAction(self.actExit)

        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._activated)
        self.tray.show()

        self._green = _dot_icon('#4bb34b')
        self._red = _dot_icon('#e64646')
        self._model: dict = {}

        self.set_model({'ready': False})

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.showRequested.emit()

    def notify(self, title: str, msg: str) -> None:
        try:
            self.tray.showMessage((title or '').strip() or 'hel zapret ui', (msg or '').strip(), QSystemTrayIcon.Information, 3000)
        except Exception:
            return

    def set_model(self, model: dict | None) -> None:
        m = model if isinstance(model, dict) else {}
        self._model = m

        ready = bool(m.get('ready', True))
        busy = bool(m.get('busy'))
        tests_running = bool(m.get('tests_running'))
        locked = (not ready) or busy or tests_running

        need_install = bool(m.get('show_install_zapret'))
        show_strategy = bool(m.get('show_strategy_select')) and (not need_install) and (not bool(m.get('external_present')))

        enabled = bool(m.get('enabled'))
        self.actToggle.setText('Выключить' if enabled else 'Включить')
        self.actToggle.setIcon(self._green if enabled else self._red)
        self.actToggle.setVisible((not need_install) and (not bool(m.get('external_present'))))
        self.actToggle.setEnabled((not locked) and self.actToggle.isVisible())

        self.actInstall.setVisible(bool(need_install))
        self.actInstall.setEnabled((not locked) and self.actInstall.isVisible())

        self.menuStrategies.menuAction().setVisible(bool(show_strategy))
        self.menuStrategies.setEnabled((not locked) and bool(show_strategy))

        if show_strategy:
            self._render_strategies(m)
        else:
            self.menuStrategies.clear()

    def _render_strategies(self, m: dict) -> None:
        cur = (m.get('current_strategy') or '') if isinstance(m.get('current_strategy'), str) else ''
        sel = (m.get('selected_strategy') or '') if isinstance(m.get('selected_strategy'), str) else ''
        strategies = m.get('strategies')
        items = list(strategies) if isinstance(strategies, list) else []

        cur_n = normalize_strategy_key(cur)
        sel_n = normalize_strategy_key(sel)

        self.menuStrategies.clear()
        for s in items:
            t = (s or '').strip()
            if not t:
                continue
            a = QAction(t, self.menuStrategies)
            a.setCheckable(True)
            n = normalize_strategy_key(t)
            a.setChecked(bool(cur_n) and (n == cur_n))
            if (not cur_n) and sel_n:
                a.setChecked(n == sel_n)
            a.triggered.connect(partial(self.applyStrategyRequested.emit, t))
            self.menuStrategies.addAction(a)


def _dot_icon(color: str) -> QIcon:
    pm = QPixmap(14, 14)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawEllipse(2, 2, 10, 10)
    p.end()
    return QIcon(pm)


