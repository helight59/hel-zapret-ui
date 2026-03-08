from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from src.services.zapret.game_filter_state import format_game_filter_status
from src.services.zapret.strategy_name import normalize_strategy_key
from src.ui.components import BusyStrip, Card, TOKENS, ToggleSwitch
from src.utils.paths import bundle_dir


def build_service_tab(tab) -> None:
    outer = QVBoxLayout(tab)
    outer.setContentsMargins(0, 0, 0, 0)
    outer.setSpacing(0)

    tab.busyStrip = BusyStrip()
    outer.addWidget(tab.busyStrip)

    tab.content = QWidget()
    outer.addWidget(tab.content, 1)

    root = QVBoxLayout(tab.content)
    root.setContentsMargins(TOKENS.space_xl, TOKENS.space_xl, TOKENS.space_xl, TOKENS.space_xl)
    root.setSpacing(TOKENS.space_l)

    top = QHBoxLayout()
    top.setSpacing(TOKENS.space_l)

    tab.cardStatus = Card('Статус')
    status = tab.cardStatus.body
    tab.lblService = QLabel('-')
    tab.lblCapture = QLabel('-')
    tab.lblStrategy = QLabel('-')
    tab.lblGameMode = QLabel('-')
    tab.lblExternal = QLabel('')
    tab.lblExternal.setProperty('muted', True)

    status.addLayout(make_status_row('Служба', tab.lblService))
    status.addLayout(make_status_row('Capture / winws', tab.lblCapture))
    status.addLayout(make_status_row('Стратегия', tab.lblStrategy))
    status.addLayout(make_status_row('Игровой режим', tab.lblGameMode))
    status.addWidget(tab.lblExternal)

    tab.cardControl = Card('Управление')
    control = tab.cardControl.body

    tab.installPanel = QWidget()
    install_layout = QVBoxLayout(tab.installPanel)
    install_layout.setContentsMargins(0, 0, 0, 0)
    install_layout.setSpacing(TOKENS.space_s)
    tab.btnInstallZapret = QPushButton('Установить')
    font = tab.btnInstallZapret.font()
    font.setPointSize(font.pointSize() + 1)
    font.setBold(True)
    tab.btnInstallZapret.setFont(font)
    tab.btnInstallZapret.setMinimumHeight(TOKENS.control_height_xl)
    tab.installHint = QLabel('')
    tab.installHint.setWordWrap(True)
    tab.installHint.setProperty('muted', True)
    install_layout.addWidget(tab.btnInstallZapret)
    install_layout.addWidget(tab.installHint)
    control.addWidget(tab.installPanel)

    tab.mainPanel = QWidget()
    main_layout = QVBoxLayout(tab.mainPanel)
    main_layout.setContentsMargins(0, 0, 0, 0)
    main_layout.setSpacing(TOKENS.space_m)

    tab.swEnabled = ToggleSwitch()
    tab.toggleText = QLabel('')
    toggle_row = QHBoxLayout()
    toggle_row.addWidget(tab.swEnabled)
    toggle_row.addWidget(tab.toggleText)
    toggle_row.addStretch(1)
    main_layout.addLayout(toggle_row)

    tab.combo = QComboBox()
    tab.combo.setMinimumWidth(260)
    tab.comboHint = QLabel('')
    tab.comboHint.setProperty('muted', True)
    main_layout.addWidget(QLabel('Стратегия'))

    strategy_row = QHBoxLayout()
    strategy_row.setSpacing(TOKENS.space_m)
    strategy_row.addWidget(tab.combo)
    tab.btnApplyStrategy = QPushButton('Применить')
    tab.btnApplyStrategy.setProperty('variant', 'secondary')
    tab.btnApplyStrategy.setMinimumWidth(128)
    strategy_row.addWidget(tab.btnApplyStrategy)
    strategy_row.addStretch(1)
    main_layout.addLayout(strategy_row)
    main_layout.addWidget(tab.comboHint)
    QTimer.singleShot(0, tab._update_strategy_width)

    remove_row = QHBoxLayout()
    tab.btnRemove = QPushButton('Удалить')
    tab.btnRemove.setProperty('variant', 'danger')
    tab.btnRemove.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    remove_row.addWidget(tab.btnRemove)
    remove_row.addStretch(1)
    main_layout.addLayout(remove_row)
    control.addWidget(tab.mainPanel)

    top.addWidget(tab.cardStatus, 1, Qt.AlignTop)
    top.addWidget(tab.cardControl, 2, Qt.AlignTop)
    root.addLayout(top)

    tab.cardWarn = Card('Предупреждения')
    warn = tab.cardWarn.body
    tab.warnText = QLabel('')
    tab.warnText.setWordWrap(True)
    tab.btnRemoveGoodbye = QPushButton('Удалить GoodbyeDPI')
    tab.btnRemoveGoodbye.setProperty('variant', 'secondary')
    warn_row = QHBoxLayout()
    warn_row.addWidget(tab.warnText, 1)
    warn_row.addWidget(tab.btnRemoveGoodbye)
    warn.addLayout(warn_row)
    root.addWidget(tab.cardWarn)
    root.addStretch(1)

    tab.installPanel.setVisible(False)
    tab.mainPanel.setVisible(False)
    tab.cardWarn.setVisible(False)


def init_background(tab) -> None:
    try:
        path = bundle_dir() / 'assets' / 'main_bg.png'
        tab._bg_src = QPixmap(str(path)) if path.exists() and path.is_file() else QPixmap()
    except Exception:
        tab._bg_src = QPixmap()
    update_background(tab)


def update_background(tab) -> None:
    if tab._bg_src.isNull():
        return
    width = max(1, int(tab.width() * 0.38 * 0.70))
    height = max(1, int(tab.height() * 0.62 * 0.70))
    pixmap = tab._bg_src.scaled(width, height, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    try:
        if not pixmap.isNull() and tab._bg_src.height() > 0:
            trim = int(round(67 * pixmap.height() / tab._bg_src.height()))
            if 0 < trim < pixmap.height():
                pixmap = pixmap.copy(0, 0, pixmap.width(), pixmap.height() - trim)
    except Exception:
        pass
    tab._bg_pm = pixmap
    tab._bg_x = max(0, tab.width() - pixmap.width() - 12)
    tab._bg_y = max(0, tab.height() - pixmap.height() - 2)
    tab.update()


def paint_background(tab) -> None:
    if tab._bg_pm.isNull():
        return
    painter = QPainter(tab)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    painter.drawPixmap(tab._bg_x, tab._bg_y, tab._bg_pm)
    painter.end()


def update_strategy_width(tab) -> None:
    try:
        base = tab.cardControl.width() or tab.width()
        button_width = tab.btnApplyStrategy.sizeHint().width() if hasattr(tab, 'btnApplyStrategy') else 0
        max_allowed = max(0, base - button_width - 80)
        if max_allowed <= 0:
            return
        if max_allowed <= 220:
            target = max_allowed
        else:
            target = int(round(max(220, int(max_allowed * 0.67)) * 1.15))
            target = min(target, max_allowed)
        if target > 0 and tab.combo.width() != target:
            tab.combo.setFixedWidth(int(target))
    except Exception:
        return


def set_combo_value(combo: QComboBox, value: str) -> None:
    if not value:
        return
    key = normalize_strategy_key(value)
    for index in range(combo.count()):
        if normalize_strategy_key(combo.itemText(index)) != key:
            continue
        if combo.currentIndex() != index:
            combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(False)
        return


def game_filter_status_text(state) -> str:
    return format_game_filter_status(state.enabled, state.runtime_game_filter_mode)


def make_status_row(label: str, value: QLabel) -> QHBoxLayout:
    row = QHBoxLayout()
    title = QLabel(label)
    title.setProperty('muted', True)
    row.addWidget(title)
    row.addStretch(1)
    row.addWidget(value)
    return row
