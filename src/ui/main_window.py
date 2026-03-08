import logging
from pathlib import Path
from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeyEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel, QHBoxLayout, QMessageBox, QScrollArea, QFrame, QSizePolicy, QStackedWidget
from src.app.config import AppConfig
from src.ui.tray import TrayController
from src.ui.tabs.service_tab import ServiceTab
from src.ui.controllers.service_controller import HomeState
from src.ui.tabs.tests_tab import TestsTab
from src.ui.tabs.settings_container_tab import SettingsContainerTab
from src.ui.tabs.about_tab import AboutTab
from src.ui.components import Sidebar, TOKENS
from src.utils.paths import bundle_dir

log = logging.getLogger('ui')


class _PrintScreenFilter(QObject):
    def __init__(self, win: 'MainWindow'):
        super().__init__(win)
        self._win = win

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.KeyPress:
            e = event
            if isinstance(e, QKeyEvent) and self._win.isActiveWindow() and e.key() in (Qt.Key_Print, Qt.Key_SysReq):
                self._win._handle_print_screen(e.modifiers())
                return True
        return super().eventFilter(obj, event)

class MainWindow(QMainWindow):
    def __init__(self, cfg: AppConfig, home_state: HomeState | None = None):
        super().__init__()
        self.cfg = cfg
        min_w, min_h = 1080, 500
        self._stable_size = None
        self._dpi_fix_in_progress = False
        self._pending_dpi_fix = False
        self._status_service = ''
        self._status_tests = ''
        self._status_about = ''
        self._status_settings = ''
        self._tests_running = False
        self._global_busy = False
        self._settings_runtime_refresh_busy = False
        self._pending_settings_service_sync = False
        self._force_exit = False
        self._route = 'home'
        self.setWindowTitle('hel zapret ui')
        try:
            w = int(self.cfg.window_width)
            h = int(self.cfg.window_height)
        except Exception:
            w, h = 1080, 560
        self.setMinimumSize(min_w, min_h)
        self.resize(max(w, min_w), max(h, min_h))
        self._stable_size = self.size()
        self.pages = QStackedWidget()
        self.service_tab = ServiceTab(self.cfg, initial_state=home_state)
        self.tests_tab = TestsTab(self.cfg)
        self.settings_tab = SettingsContainerTab(self.cfg)
        self.about_tab = AboutTab(self.cfg)

        self._route_to_idx = {
            'home': 0,
            'tests': 1,
            'settings_app': 2,
            'settings_zapret': 2,
            'settings_lists': 2,
            'about': 3,
        }
        self.pages.addWidget(self._scrollify(self.service_tab))
        self.pages.addWidget(self._scrollify(self.tests_tab))
        self.pages.addWidget(self.settings_tab)
        self.pages.addWidget(self._scrollify(self.about_tab))

        self.sidebar = Sidebar(bundle_dir() / 'assets' / 'icons')
        self.sidebar.routeSelected.connect(self._navigate)
        self.sidebar.exitRequested.connect(self._tray_exit)
        self.sidebar.set_route('home')
        root = QWidget()
        v = QVBoxLayout(root)
        v.setContentsMargins(TOKENS.space_m, TOKENS.space_m, TOKENS.space_m, TOKENS.space_s)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(TOKENS.space_m)
        body.addWidget(self.sidebar)
        body.addWidget(self.pages, 1)
        v.addLayout(body, 1)
        bottom = QHBoxLayout()
        self.appStatus = QLabel('')
        self.appStatus.setProperty('muted', True)
        self.appStatus.setVisible(False)
        bottom.addStretch(1)
        bottom.addWidget(self.appStatus)
        self.credit = QLabel('by helight')
        self.credit.setProperty('muted', True)
        bottom.addWidget(self.credit)
        v.addLayout(bottom)
        self.setCentralWidget(root)
        self.tray = TrayController()
        self.tray.toggleRequested.connect(self._tray_toggle)
        self.tray.toggleRequested.connect(lambda: log.info('tray toggle requested'))
        self.tray.installRequested.connect(self._tray_install)
        self.tray.applyStrategyRequested.connect(self._tray_apply_strategy)
        self.tray.showRequested.connect(self._tray_show)
        self.tray.showRequested.connect(lambda: log.info('tray show requested'))
        self.tray.exitRequested.connect(self._tray_exit)
        self.tray.exitRequested.connect(lambda: log.info('tray exit requested'))
        self.service_tab.trayStateChanged.connect(self._update_tray)
        self.service_tab.appStatusChanged.connect(lambda t: self._set_app_status('service', t))
        self.tests_tab.appStatusChanged.connect(lambda t: self._set_app_status('tests', t))
        self.about_tab.appStatusChanged.connect(lambda t: self._set_app_status('about', t))
        self.settings_tab.appStatusChanged.connect(lambda t: self._set_app_status('settings', t))
        self.settings_tab.globalBusyChanged.connect(self._set_global_busy)
        self.settings_tab.runtimeRefreshBusyChanged.connect(self._set_settings_runtime_refresh_busy)
        self.settings_tab.serviceSyncRequested.connect(self._sync_service_state_for_settings_restart)
        self.tests_tab.runningChanged.connect(self._set_tests_running)
        self.service_tab.stateRefreshed.connect(self._on_service_state_refreshed)
        try:
            self.settings_tab.zapretVersionChanged.connect(self.about_tab.on_zapret_version_changed)
        except Exception:
            pass

        self.settings_tab.routeSelected.connect(self._navigate)

        self._update_tray()

        self._ps_filter = _PrintScreenFilter(self)
        QGuiApplication.instance().installEventFilter(self._ps_filter)

    def _navigate(self, route: str):
        r = (route or '').strip() or 'home'
        if r not in self._route_to_idx:
            return
        if (self._tests_running or self._global_busy or self._settings_runtime_refresh_busy) and r != self._route:
            self.sidebar.set_route(self._route)
            return
        if self._route == r:
            self.sidebar.set_route(r)
            return
        self._route = r
        self.pages.setCurrentIndex(self._route_to_idx[r])
        if r in ('settings_app', 'settings_zapret', 'settings_lists'):
            self.settings_tab.set_route(r)
        self.sidebar.set_route(r)
        log.info('route changed route=%s idx=%s', r, self._route_to_idx[r])

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._dpi_fix_in_progress or self._pending_dpi_fix:
            return
        self._stable_size = self.size()

    def nativeEvent(self, eventType, message):
        try:
            if eventType == 'windows_generic_MSG':
                import ctypes
                from ctypes import wintypes

                WM_DPICHANGED = 0x02E0
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_DPICHANGED and self._stable_size is not None:
                    if not self._pending_dpi_fix:
                        self._pending_dpi_fix = True
                        QTimer.singleShot(0, self._apply_dpi_size_fix)
        except Exception:
            pass
        return super().nativeEvent(eventType, message)

    def _apply_dpi_size_fix(self):
        try:
            if self._stable_size is None:
                return
            self._dpi_fix_in_progress = True
            self.resize(self._stable_size)
        finally:
            self._dpi_fix_in_progress = False
            self._pending_dpi_fix = False

    def _scrollify(self, w: QWidget) -> QScrollArea:
        sa = QScrollArea()
        sa.setFrameShape(QFrame.NoFrame)
        sa.setWidgetResizable(True)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sa.setWidget(w)

        # Prevent vertical squish: keep a sensible minimum height, then scroll.
        try:
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            w.setMinimumHeight(max(1, w.minimumSizeHint().height()))
        except Exception:
            pass
        return sa

    def _handle_print_screen(self, mods):
        try:
            scr = None
            wh = self.windowHandle()
            if wh and wh.screen():
                scr = wh.screen()
            if not scr:
                scr = QGuiApplication.primaryScreen()
            if not scr:
                return

            if bool(mods & Qt.AltModifier):
                pm = scr.grabWindow(int(self.winId()))
            else:
                pm = scr.grabWindow(0)
            QGuiApplication.clipboard().setPixmap(pm)
            self._notify('hel zapret ui', 'Скриншот в буфере обмена')
        except Exception:
            return

    def closeEvent(self, e):
        if self._force_exit:
            super().closeEvent(e)
            return
        e.ignore()
        self.hide()

    def _tray_toggle(self):
        if self._tests_running or self._global_busy:
            return
        self.service_tab.toggle()

    def _tray_install(self):
        if self._tests_running or self._global_busy:
            return
        self.service_tab.install_zapret()

    def _tray_apply_strategy(self, strategy: str):
        if self._tests_running or self._global_busy:
            return
        self.service_tab.apply_strategy_from_tray(strategy)

    def _tray_show(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _tray_exit(self):
        self.cfg.save()
        self.tray.tray.hide()
        self._force_exit = True
        QApplication.instance().quit()

    def _notify(self, title: str, msg: str):
        return

    def _set_tests_running(self, running: bool) -> None:
        self._tests_running = bool(running)
        self.sidebar.set_locked(self._tests_running or self._global_busy or self._settings_runtime_refresh_busy)
        self.service_tab.set_tests_running(self._tests_running)
        self._update_tray()

    def confirm(self, title: str, text: str) -> bool:
        r = QMessageBox.question(self, title, text, QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return r == QMessageBox.Yes

    def _set_app_status(self, src: str, text: str):
        t = (text or '').strip()
        if src == 'service':
            self._status_service = t
        elif src == 'tests':
            self._status_tests = t
        elif src == 'about':
            self._status_about = t
        elif src == 'settings':
            self._status_settings = t
        self._render_app_status()

    def _render_app_status(self):
        t = self._status_service or self._status_tests or self._status_about or self._status_settings
        self.appStatus.setText(t)
        self.appStatus.setVisible(bool(t))


    def _set_global_busy(self, busy: bool) -> None:
        self._global_busy = bool(busy)
        self.sidebar.set_locked(self._tests_running or self._global_busy or self._settings_runtime_refresh_busy)
        self.service_tab.setEnabled(not self._global_busy)
        self.tests_tab.setEnabled(not self._global_busy)
        self.about_tab.setEnabled(not self._global_busy)
        self.settings_tab.set_global_busy(self._global_busy)
        self._update_tray()

    def _set_settings_runtime_refresh_busy(self, busy: bool) -> None:
        self._settings_runtime_refresh_busy = bool(busy)
        self.sidebar.set_locked(self._tests_running or self._global_busy or self._settings_runtime_refresh_busy)

    def _sync_service_state_for_settings_restart(self) -> None:
        self._pending_settings_service_sync = True
        self.service_tab.refresh()

    def _on_service_state_refreshed(self) -> None:
        if self._pending_settings_service_sync:
            self._pending_settings_service_sync = False
            self.settings_tab.on_service_sync_finished()
            return
        self.settings_tab.on_service_state_refreshed()

    def _update_tray(self, _ev: object | None = None):
        try:
            model = self.service_tab.get_tray_model()
        except Exception:
            model = {}
        if isinstance(model, dict):
            model['tests_running'] = bool(self._tests_running or self._global_busy)
        self.tray.set_model(model)