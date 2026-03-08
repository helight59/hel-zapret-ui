import logging
import urllib.request
import re
from pathlib import Path
from PySide6.QtCore import QUrl, QThread, Signal, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QMessageBox, QHBoxLayout
from src.app.config import AppConfig
from src.services.zapret.layout import ZapretLayout
from src.ui.adapters.state_worker import StateWorker
from src.ui.adapters.zapret_update_qt import ZapretUpdateWorker
from src.ui.controllers.service_controller import ServiceController
from src.ui.components import BusyStrip, Card, TOKENS

log = logging.getLogger('ui.about')


_WINWS_RE = re.compile(r'([A-Za-z]:\\[^"\']*?winws\.exe)', re.IGNORECASE)
_WRAP_RE = re.compile(r'([A-Za-z]:\\[^"\']*?_hel_zapret_run\.cmd)', re.IGNORECASE)

class AboutTab(QWidget):
    appStatusChanged = Signal(str)

    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg
        self.layout_z = ZapretLayout(Path(cfg.zapret_dir))
        self.service_ctrl = ServiceController(cfg)

        self._update_thread: QThread | None = None
        self._update_worker: ZapretUpdateWorker | None = None
        self._latest_thread: QThread | None = None
        self._latest_worker: StateWorker | None = None

        self._busy = False
        self._busy_text = ''

        self._local_version = ''
        self._latest_version = ''

        self.lblApp = QLabel('hel zapret ui v0.1.0')
        self.lblZapret = QLabel('zapret local: -')
        self.lblTarget = QLabel('zapret target: -')
        self.lblLatest = QLabel('zapret latest: -')
        self.lblNewer = QLabel('Есть более новая версия!')
        self.btnCheck = QPushButton('Обновить до последней версии')
        self.btnUpdate = QPushButton('Перекачать zapret')
        self.btnOpen = QPushButton('Открыть папку приложения')
        self.btnReleases = QPushButton('Открыть релизы zapret')
        self.btnDiag = QPushButton('Диагностика')
        self._build()
        self._wire()
        self.refresh()
        self.check_latest_async()

    def _build(self):
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

        card = Card('О приложении')
        v = card.body

        v.addWidget(self.lblApp)

        vv = QVBoxLayout()
        vv.setSpacing(TOKENS.space_xs - 2)
        vv.addWidget(self.lblZapret)
        vv.addWidget(self.lblTarget)
        vv.addWidget(self.lblLatest)
        self.lblNewer.setVisible(False)
        self.lblNewer.setProperty('warningText', True)
        vv.addWidget(self.lblNewer)
        v.addLayout(vv)

        row = QHBoxLayout()
        row.setSpacing(TOKENS.space_m)
        row.addWidget(self.btnCheck)
        row.addWidget(self.btnUpdate)
        row.addStretch(1)
        v.addLayout(row)

        self.btnOpen.setProperty('variant', 'secondary')
        self.btnReleases.setProperty('variant', 'secondary')
        self.btnDiag.setProperty('variant', 'secondary')
        row2 = QHBoxLayout()
        row2.setSpacing(TOKENS.space_m)
        row2.addWidget(self.btnOpen)
        row2.addWidget(self.btnReleases)
        row2.addWidget(self.btnDiag)
        row2.addStretch(1)
        v.addLayout(row2)

        root.addWidget(card)
        root.addStretch(1)

    def _wire(self):
        self.btnCheck.clicked.connect(self.update_latest)
        self.btnUpdate.clicked.connect(self.update_zapret)
        self.btnOpen.clicked.connect(self.open_app_dir)
        self.btnReleases.clicked.connect(self.open_releases)
        self.btnDiag.clicked.connect(self.show_diagnostics)

    def refresh_all(self):
        log.info('refresh_all')
        self.refresh()
        self.check_latest_async()

    def refresh(self):
        log.info('refresh local version')
        self.layout_z = ZapretLayout(Path(self.cfg.zapret_dir))
        v = (self._detect_local_version() or '').strip() or '-'
        self._local_version = '' if v == '-' else v
        self.lblZapret.setText('zapret local: ' + v)
        self._render_target()
        self._update_new_version_hint()

    def _render_target(self):
        tag = (self.cfg.zapret_version or 'latest').strip() or 'latest'
        self.lblTarget.setText('zapret target: ' + tag)

    def on_zapret_version_changed(self, _tag: str):
        self._render_target()
        self.refresh()
        self.check_latest_async()

    def _detect_local_version(self) -> str:
        v = (self.layout_z.local_version() or '').strip()
        if v:
            return v

        try:
            from src.services.zapret.detect_ps import list_winws_services, get_winws_process_path
        except Exception:
            return ''

        try:
            for s in list_winws_services():
                if (s.name or '').strip().lower() != 'zapret':
                    continue
                root = self._root_from_service_path(s.path)
                if root:
                    v2 = (ZapretLayout(root).local_version() or '').strip()
                    if v2:
                        return v2
        except Exception:
            pass

        try:
            wp = (get_winws_process_path() or '').strip().strip('"')
            if wp:
                root = self._root_from_winws_path(wp)
                if root:
                    v3 = (ZapretLayout(root).local_version() or '').strip()
                    if v3:
                        return v3
        except Exception:
            pass

        return ''

    def _root_from_service_path(self, path_raw: str) -> Path | None:
        txt = (path_raw or '').strip().replace('/', '\\')
        m = _WINWS_RE.search(txt)
        if m:
            return self._root_from_winws_path(m.group(1))
        w = _WRAP_RE.search(txt)
        if w:
            try:
                p = Path(w.group(1).strip().strip('"'))
                if p.exists() and p.is_file():
                    c = p.read_text(encoding='ascii', errors='ignore')
                    m2 = _WINWS_RE.search(c.replace('/', '\\'))
                    if m2:
                        return self._root_from_winws_path(m2.group(1))
            except Exception:
                return None
        return None

    def _root_from_winws_path(self, winws_path: str) -> Path | None:
        p = Path((winws_path or '').strip().strip('"'))
        try:
            if p.name.lower() != 'winws.exe':
                return None
            root = p.parent.parent
            if (root / 'bin' / 'winws.exe').exists():
                return root
        except Exception:
            return None
        return None

    def check_latest_async(self):
        if self._latest_thread:
            return
        log.info('check latest start')
        self.lblLatest.setText('zapret latest: ...')
        self._latest_version = ''
        self._update_new_version_hint()

        def _fetch() -> str:
            url = 'https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/main/.service/version.txt'
            return urllib.request.urlopen(url, timeout=10).read().decode('utf-8', errors='ignore').strip()

        self._latest_thread = QThread()
        self._latest_worker = StateWorker(_fetch)
        self._latest_worker.moveToThread(self._latest_thread)
        self._latest_thread.started.connect(self._latest_worker.run)
        self._latest_worker.done.connect(self._on_latest)
        self._latest_worker.error.connect(self._on_latest_err)
        self._latest_thread.start()

    def _on_latest(self, v: object):
        try:
            s = str(v or '').strip()
            self.lblLatest.setText('zapret latest: ' + (s or '-'))
            self._latest_version = s
            self._update_new_version_hint()
            log.info('check latest done value=%s', s or '-')
        finally:
            if self._latest_thread:
                self._latest_thread.quit()
                self._latest_thread.wait(2000)
            self._latest_thread = None
            self._latest_worker = None

    def _on_latest_err(self, _msg: str):
        try:
            self.lblLatest.setText('zapret latest: -')
            self._latest_version = ''
            self._update_new_version_hint()
            log.warning('check latest failed')
        finally:
            if self._latest_thread:
                self._latest_thread.quit()
                self._latest_thread.wait(2000)
            self._latest_thread = None
            self._latest_worker = None

    def update_zapret(self):
        log.info('update zapret requested')
        tag = (self.cfg.zapret_version or 'latest').strip() or 'latest'
        self._start_update(tag)

    def update_latest(self):
        log.info('update latest requested')
        latest = self._latest_value()
        local = (self._detect_local_version() or '').strip()
        if latest and local and latest.strip().lower() == local.strip().lower():
            QMessageBox.information(self, 'Обновление', 'Уже установлена последняя версия: ' + latest)
            return
        self._start_update('latest')

    def _latest_value(self) -> str:
        t = (self.lblLatest.text() or '').strip()
        if ':' not in t:
            return ''
        v = t.split(':', 1)[1].strip()
        if v in ('-', '...', ''):
            return ''
        return v

    def _norm_version(self, v: str) -> str:
        s = (v or '').strip().lower()
        if s.startswith('v'):
            s = s[1:].strip()
        return s

    def _update_new_version_hint(self):
        local = self._norm_version(self._local_version)
        latest = self._norm_version(self._latest_version)
        show = bool(local and latest and local != latest)
        self.lblNewer.setVisible(show)

    def _start_update(self, tag: str):
        if self._update_thread:
            return

        log.info('start update tag=%s', (tag or 'latest').strip() or 'latest')

        self._set_busy(True, 'Подготовка...')

        self._update_thread = QThread()
        self._update_worker = ZapretUpdateWorker(Path(self.cfg.zapret_dir), Path(self.cfg.data_dir), version_tag=(tag or 'latest').strip() or 'latest')
        self._update_worker.moveToThread(self._update_thread)
        self._update_thread.started.connect(self._update_worker.run)
        self._update_worker.stage.connect(self._set_busy_text)
        self._update_worker.done.connect(self._on_update_done)
        self._update_thread.start()

    def _on_update_done(self, ok: bool, msg: str):
        log.info('update done ok=%s msg=%s', bool(ok), msg)
        try:
            self._set_busy(False, '')
        finally:
            if self._update_thread:
                self._update_thread.quit()
                self._update_thread.wait(2000)
            self._update_thread = None
            self._update_worker = None

        if ok:
            QMessageBox.information(self, 'Обновление', 'Готово: ' + (msg or ''))
            self.refresh()
            self.check_latest_async()
        else:
            QMessageBox.critical(self, 'Обновление', msg or 'Ошибка')

    def open_app_dir(self):
        log.info('open app dir')
        from src.utils.paths import app_dir
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(app_dir())))

    def open_releases(self):
        log.info('open releases page')
        QDesktopServices.openUrl(QUrl('https://github.com/Flowseal/zapret-discord-youtube/releases'))

    def show_diagnostics(self):
        log.info('diagnostics opened')
        txt = self.service_ctrl.diagnostics_text()
        QMessageBox.information(self, 'Диагностика', txt)

    def _set_busy(self, v: bool, text: str):
        self._busy = bool(v)
        self.busyStrip.set_busy(self._busy)
        self.btnUpdate.setEnabled(not self._busy)
        self.btnCheck.setEnabled(not self._busy)
        self._set_busy_text(text)

    def _set_busy_text(self, text: str):
        t = (text or '').strip()
        self._busy_text = t
        self.appStatusChanged.emit(t if self._busy else '')