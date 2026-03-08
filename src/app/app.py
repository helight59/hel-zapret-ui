import logging
import sys
from pathlib import Path

from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox
from src.app.config import AppConfig
from src.services.windows.autostart import sync_autostart
from src.services.zapret.bootstrap import ensure_zapret_seed
from src.ui.adapters.state_worker import StateWorker
from src.ui.controllers.service_controller import ServiceController, HomeState
from src.ui.main_window import MainWindow
from src.ui.splash import SplashWindow
from src.ui.theme import apply_theme
from src.utils.icon import app_icon
from src.utils.logging_setup import setup_logging

def _has_flag(name: str) -> bool:
    return any((arg or '').strip().lower() == name for arg in sys.argv[1:])


def run_app() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName('hel zapret ui')
    if sys.platform == 'win32':
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('helight.hel_zapret_ui')
        except Exception:
            pass
    apply_theme(app)
    app.setWindowIcon(app_icon())
    start_hidden = _has_flag('--start-hidden')
    cfg = AppConfig.load()
    setup_logging(cfg)
    sync_autostart(cfg)
    ensure_zapret_seed(Path(cfg.zapret_dir))

    splash = None if start_hidden else SplashWindow()
    if splash is not None:
        splash.show()

    holder: dict[str, object] = {}

    def _cleanup_thread():
        t: QThread | None = holder.get('t') if isinstance(holder.get('t'), QThread) else None
        if t:
            t.quit()
            t.wait(2000)
        holder.pop('t', None)
        holder.pop('wkr', None)

    def _start_main(home_state: HomeState | None):
        w = MainWindow(cfg, home_state=home_state)
        holder['w'] = w
        if splash is not None:
            splash.close()
            splash.deleteLater()
        if start_hidden:
            w.hide()
            return
        w.show()

    def _on_done(st: HomeState):
        _cleanup_thread()
        _start_main(st)

    def _on_error(msg: str):
        _cleanup_thread()
        if msg:
            if start_hidden:
                logging.getLogger('app').error('startup error: %s', msg)
            else:
                QMessageBox.critical(None, 'Запуск', msg)
        _start_main(None)

    def _fetch():
        if splash is not None:
            splash.set_subtitle('Проверяем статус…')
        ctrl = ServiceController(cfg)
        t = QThread()
        wkr = StateWorker(lambda: ctrl.build_state(cfg.last_strategy or ''))
        wkr.moveToThread(t)
        t.started.connect(wkr.run)
        wkr.done.connect(_on_done)
        wkr.error.connect(_on_error)
        holder['t'] = t
        holder['wkr'] = wkr
        t.start()

    QTimer.singleShot(0, _fetch)
    return app.exec()