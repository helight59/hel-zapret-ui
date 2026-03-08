from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QEvent, QRect, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFontMetrics, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QAbstractItemView, QCheckBox, QHeaderView, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMessageBox, QPushButton, QSizePolicy, QStyledItemDelegate, QStyle, QStyleOptionViewItem, QTableView, QVBoxLayout, QWidget

from src.app.config import AppConfig
from src.services.zapret.layout import ZapretLayout
from src.services.tests.runner import RunOptions
from src.ui.adapters.tests_runner_qt import TestsRunner
from src.ui.components import BusyStrip, Card, TOKENS, install_wheel_guard
from src.ui.models.tests_table_model import BEST_DPI_ROLE, BEST_STANDARD_ROLE, TestsTableModel

log = logging.getLogger('ui.tests')

class _ColumnLeftPaddingDelegate(QStyledItemDelegate):
    def __init__(self, padding: int, parent: QWidget | None = None):
        super().__init__(parent)
        self._padding = max(0, int(padding))

    def paint(self, painter, option, index) -> None:
        opt = option
        opt.rect = option.rect.adjusted(self._padding, 0, 0, 0)
        super().paint(painter, opt, index)




class _BestBadgeDelegate(QStyledItemDelegate):
    def __init__(self, icon_path: Path, text_padding: int = 6, item_gap: int = 8, parent: QWidget | None = None):
        super().__init__(parent)
        self._text_padding = max(0, int(text_padding))
        self._item_gap = max(0, int(item_gap))
        self._pixmap = QPixmap(str(icon_path.resolve())) if icon_path.exists() else QPixmap()

    def _parts(self, index) -> list[str]:
        parts: list[str] = []
        if bool(index.data(BEST_STANDARD_ROLE)):
            parts.append('STD')
        if bool(index.data(BEST_DPI_ROLE)):
            parts.append('DPI')
        return parts

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        parts = self._parts(index)
        if self._pixmap.isNull() or not parts:
            super().paint(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ''
        opt.icon = QIcon()

        style = opt.widget.style() if opt.widget else self.parent().style()
        style.drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)

        content_rect = option.rect.adjusted(max(6, TOKENS.space_xs), 0, -max(6, TOKENS.space_xs), 0)
        icon_size = max(14, min(content_rect.height() - 4, 18))
        pm = self._pixmap.scaled(icon_size, icon_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        font_metrics = painter.fontMetrics()
        text_color = opt.palette.text().color()

        total_width = 0
        for i, part in enumerate(parts):
            total_width += font_metrics.horizontalAdvance(part) + self._text_padding + pm.width()
            if i != len(parts) - 1:
                total_width += self._item_gap

        x = content_rect.left() + max(0, (content_rect.width() - total_width) // 2)
        y = content_rect.top()
        h = content_rect.height()

        painter.save()
        painter.setPen(text_color)
        for i, part in enumerate(parts):
            text_width = font_metrics.horizontalAdvance(part)
            text_rect = QRect(x, y, text_width, h)
            painter.drawText(text_rect, int(Qt.AlignVCenter | Qt.AlignLeft), part)
            x += text_width + self._text_padding

            icon_y = y + max(0, (h - pm.height()) // 2)
            painter.drawPixmap(x, icon_y, pm)
            x += pm.width()

            if i != len(parts) - 1:
                x += self._item_gap
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        size = super().sizeHint(option, index)
        parts = self._parts(index)
        if self._pixmap.isNull() or not parts:
            return size

        font_metrics = option.fontMetrics
        icon_width = max(14, min(option.rect.height() - 4 if option.rect.height() > 0 else size.height() - 4, 18))
        total = 0
        for i, part in enumerate(parts):
            total += font_metrics.horizontalAdvance(part) + self._text_padding + icon_width
            if i != len(parts) - 1:
                total += self._item_gap
        size.setWidth(max(size.width(), total + max(12, TOKENS.space_s * 2)))
        return size


class TestsTab(QWidget):
    appStatusChanged = Signal(str)
    runningChanged = Signal(bool)

    def __init__(self, cfg: AppConfig):
        super().__init__()
        self.cfg = cfg
        self.zroot = Path(cfg.zapret_dir)
        self.layout = ZapretLayout(self.zroot)
        self.last_run_dir = ''
        self._running = False
        self._status_full = ''

        self.chkStandard = QCheckBox('Standard tests')
        self.chkDpi = QCheckBox('DPI checkers')
        self.chkStandard.setChecked(True)

        self.lblDpiNote = QLabel('DPI тесты могут занять продолжительное время.')
        self.lblDpiNote.setProperty('muted', True)

        self.list = QListWidget()
        self.list.setSelectionMode(QAbstractItemView.NoSelection)

        self.btnAll = QPushButton('Все')
        self.btnAll.setProperty('variant', 'secondary')
        self.btnNone = QPushButton('Ничего')
        self.btnNone.setProperty('variant', 'secondary')
        self.btnRun = QPushButton('Запустить')
        self.btnCancel = QPushButton('Отменить')
        self.btnCancel.setProperty('variant', 'secondary')
        self.btnCancel.setEnabled(False)

        self.btnOpenReport = QPushButton('Открыть PDF отчёт')
        self.btnOpenReport.setProperty('variant', 'secondary')
        self.btnOpenFolder = QPushButton('Открыть папку прогона')
        self.btnOpenFolder.setProperty('variant', 'secondary')
        self.btnOpenReport.setEnabled(False)
        self.btnOpenFolder.setEnabled(False)

        self.table = QTableView()
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        self.table.setFocusPolicy(Qt.NoFocus)

        table_font_px = max(11, TOKENS.font_size_sm - 1)
        header_font_px = max(10, TOKENS.font_size_sm - 2)

        table_font = self.table.font()
        table_font.setPointSize(table_font_px)
        self.table.setFont(table_font)

        header_font = self.table.horizontalHeader().font()
        header_font.setPointSize(header_font_px)
        self.table.horizontalHeader().setFont(header_font)

        header_radius = max(0, TOKENS.radius_m - 1)
        self.table.setStyleSheet(
            f'QTableView {{ font-size: {table_font_px}px; }}'
            f'QTableView::item {{ padding: 1px {max(4, TOKENS.space_s - 1)}px; }}'
            'QTableView::item:selected { background: transparent; color: palette(text); }'
            'QTableView::item:focus { outline: none; }'
            'QHeaderView { background: transparent; border: 0; }'
            'QHeaderView::section { background-clip: padding; }'
            f'QHeaderView::section {{ font-size: {header_font_px}px; padding: 3px {max(6, TOKENS.space_s)}px; border-top-left-radius: 0; border-top-right-radius: 0; }}'
            f'QHeaderView::section:first {{ border-top-left-radius: {header_radius}px; }}'
            f'QHeaderView::section:last {{ border-top-right-radius: {header_radius}px; }}'
        )
        self.table.verticalHeader().setDefaultSectionSize(22)

        self.model = TestsTableModel()
        self.table.setModel(self.model)
        self.table.setItemDelegateForColumn(0, _ColumnLeftPaddingDelegate(max(6, TOKENS.space_s), self.table))
        self.table.setItemDelegateForColumn(8, _BestBadgeDelegate(Path(__file__).resolve().parents[3] / 'assets' / 'best_badge.png', max(6, TOKENS.space_xs), 8, self.table))

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        self.table.setColumnWidth(0, 192)
        header.setSectionResizeMode(1, QHeaderView.Interactive)
        self.table.setColumnWidth(1, 56)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        self.table.setColumnWidth(2, 46)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        self.table.setColumnWidth(3, 72)
        header.setSectionResizeMode(4, QHeaderView.Interactive)
        self.table.setColumnWidth(4, 66)
        header.setSectionResizeMode(5, QHeaderView.Interactive)
        self.table.setColumnWidth(5, 66)
        for i in range(6, self.model.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)

        self.status = QLabel('')
        self.status.setMinimumWidth(0)
        self.status.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.status.setProperty('muted', True)
        self.status.installEventFilter(self)

        self.runner = TestsRunner(Path(cfg.zapret_dir), Path(cfg.data_dir))

        self._build()
        self._wire()
        install_wheel_guard(self.list, self.list.viewport())
        install_wheel_guard(self.table, self.table.viewport())
        self.refresh()

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

        self.cardSetup = Card('Параметры теста')
        setup = self.cardSetup.body

        top = QHBoxLayout()
        top.setSpacing(TOKENS.space_m)
        top.addWidget(self.chkStandard)
        top.addWidget(self.chkDpi)
        top.addStretch(1)
        top.addWidget(self.btnAll)
        top.addWidget(self.btnNone)
        top.addWidget(self.btnRun)
        top.addWidget(self.btnCancel)
        setup.addLayout(top)
        setup.addWidget(self.lblDpiNote)
        self.list.setMinimumHeight(220)
        setup.addWidget(self.list)

        self.cardResults = Card('Прогресс и результаты')
        results = self.cardResults.body
        self.table.setMinimumHeight(280)
        results.addWidget(self.table, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(TOKENS.space_m)
        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.btnOpenReport)
        bottom.addWidget(self.btnOpenFolder)
        results.addLayout(bottom)

        root.addWidget(self.cardSetup)
        root.addWidget(self.cardResults, 1)

    def _wire(self) -> None:
        self.btnAll.clicked.connect(self.select_all)
        self.btnNone.clicked.connect(self.select_none)
        self.btnRun.clicked.connect(self.run_tests)
        self.btnCancel.clicked.connect(self.cancel_tests)
        self.btnOpenReport.clicked.connect(self.open_report)
        self.btnOpenFolder.clicked.connect(self.open_folder)

        self.runner.runStarted.connect(self._on_started)
        self.runner.runFinished.connect(self._on_finished)
        self.runner.progressUpdated.connect(self._on_progress)

    def eventFilter(self, obj, event):
        if obj is self.status and event.type() == QEvent.Resize:
            self._update_status_elide()
        return super().eventFilter(obj, event)

    def _set_status(self, text: str) -> None:
        self._status_full = text or ''
        self._update_status_elide()

    def _update_status_elide(self) -> None:
        if not self._status_full:
            self.status.setText('')
            self.status.setToolTip('')
            return
        width = max(0, int(self.status.width()) - 4)
        short = QFontMetrics(self.status.font()).elidedText(self._status_full, Qt.ElideRight, width)
        self.status.setText(short)
        self.status.setToolTip(self._status_full if short != self._status_full else '')

    def _set_running(self, running: bool) -> None:
        self._running = bool(running)
        self.runningChanged.emit(self._running)
        self.busyStrip.set_busy(self._running)

        self.chkStandard.setEnabled(not running)
        self.chkDpi.setEnabled(not running)
        self.list.setEnabled(not running)
        self.btnAll.setEnabled(not running)
        self.btnNone.setEnabled(not running)
        self.btnRun.setEnabled(not running)
        self.btnCancel.setEnabled(running)
        self.btnOpenReport.setEnabled((not running) and bool(self.last_run_dir))
        self.btnOpenFolder.setEnabled((not running) and bool(self.last_run_dir))

    def refresh(self) -> None:
        self.zroot = Path(self.cfg.zapret_dir)
        self.layout = ZapretLayout(self.zroot)
        log.info('refresh strategies zapret_dir=%s ok=%s', str(self.zroot), bool(self.layout.ok()))
        self.list.clear()
        for strategy in self.layout.list_strategies():
            item = QListWidgetItem(strategy)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.list.addItem(item)

    def select_all(self) -> None:
        log.info('select all strategies')
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.Checked)

    def select_none(self) -> None:
        log.info('select none strategies')
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(Qt.Unchecked)

    def _selected(self) -> list[str]:
        out: list[str] = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == Qt.Checked:
                out.append(item.text())
        return out

    def run_tests(self) -> None:
        log.info('run tests clicked standard=%s dpi=%s', bool(self.chkStandard.isChecked()), bool(self.chkDpi.isChecked()))
        if not self.layout.ok():
            QMessageBox.critical(self, 'zapret', 'Папка zapret некорректна. Проверь путь в настройках.')
            return
        if (not self.chkStandard.isChecked()) and (not self.chkDpi.isChecked()):
            QMessageBox.warning(self, 'Тесты', 'Выбери хотя бы один тип тестов.')
            return

        strategies = self._selected()
        log.info('run tests selected strategies=%d', len(strategies))
        if not strategies:
            QMessageBox.warning(self, 'Тесты', 'Нужно выбрать стратегии.')
            return

        self.last_run_dir = ''
        self.btnOpenReport.setEnabled(False)
        self.btnOpenFolder.setEnabled(False)

        rows = []
        for i, strategy in enumerate(strategies):
            rows.append({
                'name': strategy,
                'batch': f'{i + 1}/{len(strategies)}',
                'now': '',
                'standard': 'QUEUED' if self.chkStandard.isChecked() else '—',
                'std_http': '',
                'std_ping': '',
                'dpi': 'QUEUED' if self.chkDpi.isChecked() else '—',
                'dpi_suite': '',
                'best_standard': False,
                'best_dpi': False,
            })
        self.model.set_rows(rows)

        self._set_running(True)
        self._set_status('Запуск...')
        self.appStatusChanged.emit('Запуск...')
        self.runner.start(RunOptions(standard=self.chkStandard.isChecked(), dpi=self.chkDpi.isChecked(), strategies=strategies))

    def cancel_tests(self) -> None:
        log.info('cancel tests clicked')
        self.btnCancel.setEnabled(False)
        self._set_status('Отмена...')
        self.appStatusChanged.emit('Отмена...')
        self.runner.cancel()

    def _on_started(self) -> None:
        log.info('tests started')

    def _on_progress(self, event: object) -> None:
        if not isinstance(event, dict):
            return

        kind = (event.get('kind') or '') if isinstance(event.get('kind'), str) else ''
        row = event.get('row')
        cfg = (event.get('config') or '') if isinstance(event.get('config'), str) else ''
        batch = (event.get('batch') or '') if isinstance(event.get('batch'), str) else ''
        phase = (event.get('phase') or '') if isinstance(event.get('phase'), str) else ''
        step = (event.get('step') or '') if isinstance(event.get('step'), str) else ''

        if isinstance(row, int):
            for i in range(len(self.model.rows)):
                patch: dict[str, object] = {}

                if kind == 'dpi' and self.model.rows[i].get('standard') == 'RUNNING':
                    patch['standard'] = 'DONE'

                if i == row:
                    patch['now'] = 'STD' if kind == 'standard' else ('DPI' if kind == 'dpi' else '')
                    if kind == 'standard' and (self.model.rows[i].get('standard') in {'QUEUED', 'RUNNING'}):
                        patch['standard'] = 'RUNNING'
                    if kind == 'dpi' and (self.model.rows[i].get('dpi') in {'QUEUED', 'RUNNING'}):
                        patch['dpi'] = 'RUNNING'
                else:
                    if self.model.rows[i].get('now'):
                        patch['now'] = ''
                    if kind == 'standard' and self.model.rows[i].get('standard') == 'RUNNING':
                        patch['standard'] = 'DONE'
                    if kind == 'dpi' and self.model.rows[i].get('dpi') == 'RUNNING':
                        patch['dpi'] = 'DONE'

                if patch:
                    self.model.update_row(i, patch)

        if cfg:
            prefix = 'STD' if kind == 'standard' else ('DPI' if kind == 'dpi' else '')
            message = f'{prefix} {batch} — {cfg}' if prefix else f'{batch} — {cfg}'
            if phase == 'step' and step:
                message += f' — {step}'
            self._set_status(message)
            self.appStatusChanged.emit(message)

    def _on_finished(self, status: str, payload: str) -> None:
        log.info('tests finished status=%s payload=%s', status, payload)
        try:
            if status not in {'OK', 'CANCELLED'}:
                self._set_status('Ошибка: ' + payload)
                QMessageBox.critical(self, 'Тесты', payload)
                return

            self.last_run_dir = payload
            self._set_status('Отменено: ' + payload if status == 'CANCELLED' else 'Готово: ' + payload)
            self.btnOpenReport.setEnabled(True)
            self.btnOpenFolder.setEnabled(True)

            try:
                import json

                run_file = Path(payload) / 'run.json'
                obj = json.loads(run_file.read_text(encoding='utf-8'))

                restore = obj.get('restore') or {}
                if isinstance(restore, dict):
                    ok = bool(restore.get('ok'))
                    msg = (restore.get('message') or '') if isinstance(restore.get('message'), str) else ''
                    if not ok:
                        QMessageBox.warning(self, 'Тесты', 'Тесты завершены, но восстановить zapret не получилось.\n\n' + (msg or ''))

                rows = []
                for result in obj.get('results', []):
                    rows.append({
                        'name': result.get('name', ''),
                        'batch': result.get('batch', ''),
                        'now': '',
                        'standard': result.get('standard', ''),
                        'std_http': _fmt_std_http(result),
                        'std_ping': _fmt_std_ping(result),
                        'dpi': result.get('dpi', ''),
                        'dpi_suite': _fmt_dpi_suite(result),
                        'best_standard': bool(result.get('best_standard')),
                        'best_dpi': bool(result.get('best_dpi')),
                    })
                self.model.set_rows(rows)
            except Exception:
                pass
        finally:
            self._set_running(False)
            self.appStatusChanged.emit('')

    def open_report(self) -> None:
        log.info('open_report clicked')
        if not self.last_run_dir:
            return
        report = Path(self.last_run_dir) / 'report.pdf'
        if report.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(report)))

    def open_folder(self) -> None:
        log.info('open_folder clicked')
        if not self.last_run_dir:
            return
        folder = Path(self.last_run_dir)
        if folder.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


def _fmt_std_http(result: dict) -> str:
    try:
        ok = int(result.get('std_http_ok') or 0)
        err = int(result.get('std_http_err') or 0)
        unsup = int(result.get('std_http_unsup') or 0)
        total = ok + err + unsup
        if total <= 0:
            return ''
        return f'{ok}/{err}/{unsup}'
    except Exception:
        return ''


def _fmt_std_ping(result: dict) -> str:
    try:
        ok = int(result.get('std_ping_ok') or 0)
        fail = int(result.get('std_ping_fail') or 0)
        total = ok + fail
        if total <= 0:
            return ''
        return f'{ok}/{fail}'
    except Exception:
        return ''


def _fmt_dpi_suite(result: dict) -> str:
    try:
        ok = int(result.get('dpi_ok') or 0)
        fail = int(result.get('dpi_fail') or 0)
        unsup = int(result.get('dpi_unsup') or 0)
        blocked = int(result.get('dpi_blocked') or 0)
        total = ok + fail + unsup + blocked
        if total <= 0:
            return ''
        return f'{ok}/{fail}/{unsup}/{blocked}'
    except Exception:
        return ''
