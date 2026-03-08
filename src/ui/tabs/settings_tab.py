from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout, QWidget

from src.app.config import AppConfig
from src.services.windows.autostart import sync_autostart
from src.services.zapret.catalog import ZapretVersionItem, available_versions
from src.services.zapret.layout import ZapretLayout
from src.ui.adapters.state_worker import StateWorker
from src.ui.adapters.zapret_update_qt import ZapretUpdateWorker
from src.ui.components import BusyStrip, Card, TOKENS
from src.ui.tabs.settings_tab_cache import cache_size_bytes, clear_cache, fmt_bytes
from src.ui.tabs.settings_tab_dialogs import InstallDialog
from src.ui.tabs.settings_tab_versions import current_tag, effective_version, select_tag, update_switch_button, update_version_hint


log = logging.getLogger('ui.settings')


class SettingsTab(QWidget):
    zapretVersionChanged = Signal(str)

    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.setFocusPolicy(Qt.StrongFocus)
        self.cfg = cfg

        self._install_thread: QThread | None = None
        self._install_worker: ZapretUpdateWorker | None = None
        self._versions_thread: QThread | None = None
        self._versions_worker: StateWorker | None = None
        self._versions: list[ZapretVersionItem] = []
        self._tag_to_version: dict[str, str] = {}
        self._latest_resolved_version = ''
        self._cache_size_thread: QThread | None = None
        self._cache_size_worker: StateWorker | None = None
        self._cache_clear_thread: QThread | None = None
        self._cache_clear_worker: StateWorker | None = None

        self._build()
        self._wire()
        self._load_versions()
        self._refresh_cache_size()

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

        self.cardPaths = Card('Пути')
        paths = self.cardPaths.body
        self.lblPathsHint = QLabel('Лучше не трогать, если всё работает. Меняй только если понимаешь, что делаешь.')
        self.lblPathsHint.setWordWrap(True)
        self.lblPathsHint.setProperty('muted', True)
        paths.addWidget(self.lblPathsHint)

        path_row = QHBoxLayout()
        path_row.addWidget(QLabel('Папка zapret'))
        self.lblZapretFixed = QLabel(str(Path(self.cfg.zapret_dir)))
        self.lblZapretFixed.setProperty('muted', True)
        path_row.addWidget(self.lblZapretFixed, 1)
        paths.addLayout(path_row)

        data_row = QHBoxLayout()
        data_row.addWidget(QLabel('Data dir'))
        self.edData = QLineEdit(self.cfg.data_dir)
        self.btnData = QPushButton('...')
        self.btnData.setProperty('variant', 'secondary')
        self.btnData.setFocusPolicy(Qt.NoFocus)
        data_row.addWidget(self.edData, 1)
        data_row.addWidget(self.btnData)
        paths.addLayout(data_row)

        self.cardBehavior = Card('Поведение')
        behavior = self.cardBehavior.body
        self.lblTrayHint = QLabel("Приложение всегда работает в трее. Закрытие окна не завершает процесс — для выхода используй пункт 'Выход' в трее.")
        self.lblTrayHint.setWordWrap(True)
        self.lblTrayHint.setProperty('muted', True)
        self.chkAutostart = QCheckBox('Запускать вместе с Windows')
        self.chkAutostart.setChecked(bool(self.cfg.autostart_enabled))
        self.chkRemoveWd = QCheckBox('При удалении служб также удалять WinDivert')
        self.chkRemoveWd.setChecked(self.cfg.remove_windivert_on_remove)
        self.lblAutostartHint = QLabel('При входе в Windows приложение стартует сразу в трее, без открытия окна.')
        self.lblAutostartHint.setWordWrap(True)
        self.lblAutostartHint.setProperty('muted', True)
        behavior.addWidget(self.lblTrayHint)
        behavior.addWidget(self.chkAutostart)
        behavior.addWidget(self.lblAutostartHint)
        behavior.addWidget(self.chkRemoveWd)

        self.cardInstall = Card('Установка zapret')
        install = self.cardInstall.body
        version_row = QHBoxLayout()
        version_row.addWidget(QLabel('Версия (начиная с 1.9.4)'))
        self.cmbVersion = QComboBox()
        self.cmbVersion.setMinimumWidth(220)
        version_row.addWidget(self.cmbVersion)
        self.btnRefreshVersions = QPushButton('Обновить список')
        self.btnRefreshVersions.setProperty('variant', 'secondary')
        self.btnRefreshVersions.setFocusPolicy(Qt.NoFocus)
        version_row.addWidget(self.btnRefreshVersions)
        self.btnSwitchVersion = QPushButton('Сменить версию')
        self.btnSwitchVersion.setFocusPolicy(Qt.NoFocus)
        self.btnSwitchVersion.setVisible(False)
        version_row.addWidget(self.btnSwitchVersion)
        version_row.addStretch(1)
        install.addLayout(version_row)

        self.lblVersionHint = QLabel('')
        self.lblVersionHint.setProperty('muted', True)
        install.addWidget(self.lblVersionHint)

        self.cardCache = Card('Кеш')
        cache = self.cardCache.body
        cache_row = QHBoxLayout()
        cache_row.addWidget(QLabel('Размер кеша'))
        self.lblCacheSize = QLabel('—')
        self.lblCacheSize.setProperty('muted', True)
        cache_row.addWidget(self.lblCacheSize, 1)
        self.btnClearCache = QPushButton('Очистить')
        self.btnClearCache.setProperty('variant', 'secondary')
        self.btnClearCache.setFocusPolicy(Qt.NoFocus)
        cache_row.addWidget(self.btnClearCache)
        cache.addLayout(cache_row)

        self.lblCacheHint = QLabel('Сюда попадают логи, история тестов, кэш списка релизов и бэкапы после переустановки. Очистка не трогает настройки и папку zapret.')
        self.lblCacheHint.setWordWrap(True)
        self.lblCacheHint.setProperty('muted', True)
        cache.addWidget(self.lblCacheHint)

        root.addWidget(self.cardBehavior)
        root.addWidget(self.cardInstall)
        root.addWidget(self.cardCache)
        root.addWidget(self.cardPaths)
        root.addStretch(1)

    def _wire(self) -> None:
        self.btnData.clicked.connect(self.pick_data)
        self.btnSwitchVersion.clicked.connect(self.switch_version)
        self.btnRefreshVersions.clicked.connect(self._load_versions)
        self.cmbVersion.currentIndexChanged.connect(self._version_selected)
        self.btnClearCache.clicked.connect(self._clear_cache)
        self.chkAutostart.toggled.connect(self._save_general)
        self.chkRemoveWd.toggled.connect(self._save_general)
        self.edData.editingFinished.connect(self._save_general)

    def _defocus(self) -> None:
        try:
            self.edData.clearFocus()
        except Exception:
            pass
        try:
            self.setFocus(Qt.OtherFocusReason)
        except Exception:
            pass

    def pick_data(self) -> None:
        self._defocus()
        log.info('pick data dir opened')
        directory = QFileDialog.getExistingDirectory(self, 'Выбери папку данных', self.edData.text().strip() or str(Path.cwd()))
        if directory:
            log.info('pick data dir selected=%s', directory)
            self.edData.setText(directory)
            self._save_general()
        self._defocus()

    def _save_general(self) -> None:
        old_data = (self.cfg.data_dir or '').strip()
        new_data = (self.edData.text().strip() or old_data).strip()
        prev_remove = bool(self.cfg.remove_windivert_on_remove)
        prev_autostart = bool(self.cfg.autostart_enabled)

        self.cfg.data_dir = new_data or old_data
        self.cfg.autostart_enabled = self.chkAutostart.isChecked()
        self.cfg.remove_windivert_on_remove = self.chkRemoveWd.isChecked()
        self.cfg.save()

        if (new_data or '') != (old_data or ''):
            log.info('settings changed data_dir: %s -> %s', old_data, new_data)
        if bool(self.cfg.autostart_enabled) != prev_autostart:
            log.info('settings changed autostart_enabled=%s', bool(self.cfg.autostart_enabled))
            result = sync_autostart(self.cfg)
            if not result.ok:
                QMessageBox.warning(self, 'Автозапуск', result.message or 'Не удалось обновить автозапуск Windows.')
        if bool(self.cfg.remove_windivert_on_remove) != prev_remove:
            log.info('settings changed remove_windivert_on_remove=%s', bool(self.cfg.remove_windivert_on_remove))

        try:
            self.lblZapretFixed.setText(str(Path(self.cfg.zapret_dir)))
        except Exception:
            pass
        if (new_data or '') != (old_data or ''):
            self._load_versions()
        self._refresh_cache_size()
        self._update_switch_button()

    def switch_version(self) -> None:
        self._defocus()
        if self._install_thread:
            return
        tag = (self._current_tag() or '').strip()
        if not tag:
            return

        log.info('switch version requested tag=%s', tag)
        wanted = self._effective_version(tag) or tag
        answer = QMessageBox.question(
            self,
            'Смена версии',
            f'Установить версию zapret: {wanted}?\nБудут остановлены/удалены другие winws-службы и процессы.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            self._defocus()
            return

        dialog = InstallDialog('Смена версии', 'Подготовка...', self)
        self._install_thread = QThread()
        self._install_worker = ZapretUpdateWorker(Path(self.cfg.zapret_dir), Path(self.cfg.data_dir), version_tag=tag)
        self._install_worker.moveToThread(self._install_thread)
        self._install_thread.started.connect(self._install_worker.run)
        self._install_worker.stage.connect(dialog.set_text)
        self._install_worker.done.connect(lambda ok, msg: self._install_done(ok, msg, dialog, tag))
        dialog.btnCancel.clicked.connect(self._install_worker.cancel)

        self.btnSwitchVersion.setEnabled(False)
        self._install_thread.start()
        dialog.exec()
        self._defocus()

    def _install_done(self, ok: bool, msg: str, dialog: InstallDialog, tag: str) -> None:
        try:
            dialog.close()
        except Exception:
            pass
        if self._install_thread:
            self._install_thread.quit()
            self._install_thread.wait(500)
        self._install_thread = None
        self._install_worker = None

        if ok:
            self.cfg.zapret_version = (tag or 'latest').strip() or 'latest'
            self.cfg.save()
            try:
                self.zapretVersionChanged.emit(self.cfg.zapret_version)
            except Exception:
                pass

        self.btnSwitchVersion.setEnabled(True)
        self._update_version_hint()
        self._update_switch_button()
        if ok:
            QMessageBox.information(self, 'Смена версии', msg)
        else:
            QMessageBox.critical(self, 'Смена версии', msg)
        self._defocus()

    def _load_versions(self) -> None:
        if self._versions_thread:
            return
        self._defocus()
        log.info('load versions requested')
        self.btnRefreshVersions.setEnabled(False)
        self.cmbVersion.setEnabled(False)
        self.lblVersionHint.setText('Загружаем список релизов...')

        self._versions_thread = QThread()
        self._versions_worker = StateWorker(lambda: available_versions(Path(self.cfg.data_dir), min_version='1.9.4'))
        self._versions_worker.moveToThread(self._versions_thread)
        self._versions_thread.started.connect(self._versions_worker.run)
        self._versions_worker.done.connect(self._on_versions)
        self._versions_worker.error.connect(self._on_versions_error)
        self._versions_thread.start()

    def _on_versions(self, items: list[ZapretVersionItem]) -> None:
        try:
            self._versions = items or []
            log.info('versions loaded count=%d', len(self._versions))
            self._tag_to_version = {}
            self._latest_resolved_version = ''
            for item in self._versions:
                if (item.tag or '').strip() == 'latest':
                    continue
                self._tag_to_version[str(item.tag)] = str(item.label)
                if not self._latest_resolved_version:
                    self._latest_resolved_version = str(item.label)

            self.cmbVersion.blockSignals(True)
            self.cmbVersion.clear()
            for item in self._versions:
                title = item.label
                if item.published_at:
                    title = f'{item.label} ({item.published_at[:10]})'
                self.cmbVersion.addItem(title, item.tag)
            self.cmbVersion.blockSignals(False)

            select_tag(self.cmbVersion, (self.cfg.zapret_version or 'latest').strip() or 'latest')
            self._update_version_hint()
            self._update_switch_button()
        finally:
            self._cleanup_versions_thread()
            self._refresh_cache_size()

    def _on_versions_error(self, msg: str) -> None:
        try:
            self.lblVersionHint.setText('Не удалось загрузить список релизов (проверь интернет).')
            log.warning('versions load failed: %s', msg or 'unknown')
        finally:
            self._cleanup_versions_thread()

    def _cleanup_versions_thread(self) -> None:
        if self._versions_thread:
            self._versions_thread.quit()
            self._versions_thread.wait(2000)
        self._versions_thread = None
        self._versions_worker = None
        self.btnRefreshVersions.setEnabled(True)
        self.cmbVersion.setEnabled(True)

    def _version_selected(self) -> None:
        self._update_version_hint()
        self._update_switch_button()

    def _current_tag(self) -> str:
        return current_tag(self)

    def _update_version_hint(self) -> None:
        update_version_hint(self)

    def _installed_version(self) -> str:
        try:
            return (ZapretLayout(Path(self.cfg.zapret_dir)).local_version() or '').strip()
        except Exception:
            return ''

    def _effective_version(self, tag: str) -> str:
        return effective_version(self, tag)

    def _update_switch_button(self) -> None:
        update_switch_button(self)

    def _refresh_cache_size(self) -> None:
        if self._cache_size_thread:
            return
        data_dir = Path(self.cfg.data_dir)
        self.lblCacheSize.setText('считаем...')
        self.btnClearCache.setEnabled(False)

        self._cache_size_thread = QThread()
        self._cache_size_worker = StateWorker(lambda: cache_size_bytes(data_dir))
        self._cache_size_worker.moveToThread(self._cache_size_thread)
        self._cache_size_thread.started.connect(self._cache_size_worker.run)
        self._cache_size_worker.done.connect(self._on_cache_size)
        self._cache_size_worker.error.connect(self._on_cache_size_error)
        self._cache_size_thread.start()

    def _on_cache_size(self, size: int) -> None:
        try:
            self.lblCacheSize.setText(fmt_bytes(int(size or 0)))
            self.btnClearCache.setEnabled(int(size or 0) > 0)
            log.info('cache size bytes=%s', int(size or 0))
        finally:
            if self._cache_size_thread:
                self._cache_size_thread.quit()
                self._cache_size_thread.wait(2000)
            self._cache_size_thread = None
            self._cache_size_worker = None

    def _on_cache_size_error(self, _msg: str) -> None:
        try:
            self.lblCacheSize.setText('—')
            self.btnClearCache.setEnabled(True)
        finally:
            if self._cache_size_thread:
                self._cache_size_thread.quit()
                self._cache_size_thread.wait(2000)
            self._cache_size_thread = None
            self._cache_size_worker = None

    def _clear_cache(self) -> None:
        if self._cache_clear_thread:
            return
        answer = QMessageBox.question(
            self,
            'Очистка кеша',
            'Удалить кеш (логи/историю/бэкапы/кэш релизов)? Настройки и папка zapret не будут тронуты.',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return

        log.info('clear cache requested')
        self.btnClearCache.setEnabled(False)
        self.lblCacheSize.setText('очищаем...')
        data_dir = Path(self.cfg.data_dir)

        self._cache_clear_thread = QThread()
        self._cache_clear_worker = StateWorker(lambda: clear_cache(data_dir))
        self._cache_clear_worker.moveToThread(self._cache_clear_thread)
        self._cache_clear_thread.started.connect(self._cache_clear_worker.run)
        self._cache_clear_worker.done.connect(self._on_cache_cleared)
        self._cache_clear_worker.error.connect(self._on_cache_cleared_error)
        self._cache_clear_thread.start()

    def _on_cache_cleared(self, _value: object) -> None:
        try:
            log.info('clear cache done')
            self._refresh_cache_size()
        finally:
            if self._cache_clear_thread:
                self._cache_clear_thread.quit()
                self._cache_clear_thread.wait(2000)
            self._cache_clear_thread = None
            self._cache_clear_worker = None

    def _on_cache_cleared_error(self, _msg: str) -> None:
        try:
            log.warning('clear cache failed')
            self._refresh_cache_size()
        finally:
            if self._cache_clear_thread:
                self._cache_clear_thread.quit()
                self._cache_clear_thread.wait(2000)
            self._cache_clear_thread = None
            self._cache_clear_worker = None
