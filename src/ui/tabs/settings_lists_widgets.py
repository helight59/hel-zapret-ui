from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QVBoxLayout, QWidget

from src.services.zapret.user_lists import normalize_entries
from src.ui.components import Card, TOKENS, install_wheel_guard


class EntryDialog(QDialog):
    def __init__(self, title: str, description: str, placeholder: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle(title)
        self.resize(420, 0)

        root = QVBoxLayout(self)
        root.setContentsMargins(TOKENS.space_l + 2, TOKENS.space_l + 2, TOKENS.space_l + 2, TOKENS.space_l + 2)
        root.setSpacing(TOKENS.space_m)

        self.lblDescription = QLabel(description)
        self.lblDescription.setWordWrap(True)
        self.lblDescription.setProperty('muted', True)
        root.addWidget(self.lblDescription)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText(placeholder)
        root.addWidget(self.edit)

        self.lblError = QLabel('')
        self.lblError.setWordWrap(True)
        self.lblError.setProperty('dangerText', True)
        self.lblError.setVisible(False)
        root.addWidget(self.lblError)

        row = QHBoxLayout()
        row.addStretch(1)
        self.btnCancel = QPushButton('Отмена')
        self.btnCancel.setProperty('variant', 'secondary')
        row.addWidget(self.btnCancel)
        self.btnOk = QPushButton('Добавить')
        row.addWidget(self.btnOk)
        root.addLayout(row)

        self.btnCancel.clicked.connect(self.reject)
        self.btnOk.clicked.connect(self._accept)
        self.edit.returnPressed.connect(self._accept)

    def _accept(self) -> None:
        if not self.value():
            self.lblError.setText('Нужна хотя бы одна запись.')
            self.lblError.setVisible(True)
            return
        self.accept()

    def value(self) -> str:
        return str(self.edit.text() or '').strip()


class RoundIconButton(QPushButton):
    def __init__(self, icon: QIcon, tooltip: str, parent: QWidget | None = None):
        super().__init__('', parent)
        self.setProperty('smallRoundButton', True)
        self.setProperty('listAddButton', True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setFixedSize(28, 28)
        self.setIcon(icon)
        self.setIconSize(QSize(14, 14))
        self.setFocusPolicy(Qt.NoFocus)


class RowActionButton(QPushButton):
    def __init__(self, icon: QIcon, tooltip: str, parent: QWidget | None = None):
        super().__init__('', parent)
        self.setProperty('rowAction', True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)
        self.setFixedSize(24, 24)
        self.setIcon(icon)
        self.setIconSize(QSize(14, 14))
        self.setFocusPolicy(Qt.NoFocus)


class EditableListCard(Card):
    changed = Signal()

    def __init__(self, title: str, description: str, add_title: str, add_description: str, placeholder: str, delete_icon: QIcon, add_icon: QIcon, parent: QWidget | None = None):
        super().__init__(title, parent)
        self._entries: list[str] = []
        self._add_title = add_title
        self._add_description = add_description
        self._placeholder = placeholder
        self._delete_icon = delete_icon
        self._add_icon = add_icon
        self._row_height = 34
        self._row_spacing = 0

        body = self.body
        self.lblDescription = QLabel(description)
        self.lblDescription.setWordWrap(True)
        self.lblDescription.setProperty('muted', True)
        body.addWidget(self.lblDescription)

        tools = QHBoxLayout()
        tools.setSpacing(TOKENS.space_s)
        self.lblCount = QLabel('0 записей')
        self.lblCount.setProperty('muted', True)
        tools.addWidget(self.lblCount)
        tools.addStretch(1)
        self.btnAdd = RoundIconButton(self._add_icon, add_title)
        tools.addWidget(self.btnAdd)
        body.addLayout(tools)

        self.listWrap = QFrame()
        self.listWrap.setProperty('listWrap', True)
        wrap_layout = QVBoxLayout(self.listWrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.setSpacing(0)

        self.listScroll = QScrollArea()
        self.listScroll.setFrameShape(QFrame.NoFrame)
        self.listScroll.setWidgetResizable(True)
        self.listScroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.listScroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.listScroll.setFocusPolicy(Qt.NoFocus)
        self.listScroll.viewport().setAutoFillBackground(False)

        self.listContent = QWidget()
        self.listLayout = QVBoxLayout(self.listContent)
        self.listLayout.setContentsMargins(0, 0, 0, 0)
        self.listLayout.setSpacing(self._row_spacing)
        self.listLayout.addStretch(1)

        self.listScroll.setWidget(self.listContent)
        install_wheel_guard(self.listScroll)
        wrap_layout.addWidget(self.listScroll)
        body.addWidget(self.listWrap)

        self.lblEmpty = QLabel('Пока пусто.')
        self.lblEmpty.setProperty('muted', True)
        body.addWidget(self.lblEmpty)

        self.btnAdd.clicked.connect(self._on_add_clicked)
        self._refresh_state()

    def set_entries(self, values: list[str]) -> None:
        self._entries = normalize_entries(values)
        self._rebuild_rows()

    def entries(self) -> list[str]:
        return list(self._entries)

    def _on_add_clicked(self) -> None:
        dialog = EntryDialog(self._add_title, self._add_description, self._placeholder, self)
        if dialog.exec() != QDialog.Accepted:
            return
        value = dialog.value()
        next_values = normalize_entries([*self._entries, value])
        if len(next_values) == len(self._entries):
            return
        self._entries = next_values
        self._rebuild_rows()
        self.changed.emit()

    def _remove_at(self, row: int) -> None:
        if row < 0 or row >= len(self._entries):
            return
        del self._entries[row]
        self._rebuild_rows()
        self.changed.emit()

    def _clear_rows(self) -> None:
        while self.listLayout.count() > 1:
            item = self.listLayout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _rebuild_rows(self) -> None:
        self._clear_rows()
        for row, value in enumerate(self._entries):
            alt = bool(row % 2)
            row_widget = QFrame()
            row_widget.setProperty('listEntryRow', True)
            row_widget.setProperty('alternateRow', alt)
            row_widget.setFixedHeight(self._row_height)
            row_widget.setFocusPolicy(Qt.NoFocus)

            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(TOKENS.space_m - 2, TOKENS.space_xs - 1, TOKENS.space_s - 2, TOKENS.space_xs - 1)
            row_layout.setSpacing(TOKENS.space_s)

            label = QLabel(value)
            label.setProperty('listEntryText', True)
            label.setTextInteractionFlags(Qt.NoTextInteraction)
            label.setFocusPolicy(Qt.NoFocus)
            label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            row_layout.addWidget(label, 1, Qt.AlignVCenter)

            btn_remove = RowActionButton(self._delete_icon, 'Удалить из списка')
            btn_remove.clicked.connect(lambda _checked=False, current_row=row: self._remove_at(current_row))
            row_layout.addWidget(btn_remove, 0, Qt.AlignVCenter | Qt.AlignRight)

            self.listLayout.insertWidget(self.listLayout.count() - 1, row_widget)
        self._refresh_state()

    def _refresh_state(self) -> None:
        count = len(self._entries)
        self.lblCount.setText(f'{count} {entries_word(count)}')
        empty = count == 0
        self.lblEmpty.setVisible(empty)
        self.listWrap.setVisible(not empty)
        visible_rows = min(max(count, 1), 4)
        spacing = self._row_spacing * max(visible_rows - 1, 0)
        inner_height = visible_rows * self._row_height + spacing
        self.listScroll.setFixedHeight(inner_height)
        self.listWrap.setFixedHeight(inner_height + 2)


def make_padded_icon(path: Path, padding: int = 0) -> QIcon:
    pixmap = QPixmap(str(path.resolve()))
    if pixmap.isNull():
        return QIcon(str(path.resolve()))

    image = pixmap.toImage().convertToFormat(QImage.Format_ARGB32)
    left = image.width()
    top = image.height()
    right = -1
    bottom = -1
    for y in range(image.height()):
        for x in range(image.width()):
            if image.pixelColor(x, y).alpha() <= 0:
                continue
            left = min(left, x)
            top = min(top, y)
            right = max(right, x)
            bottom = max(bottom, y)

    if right < left or bottom < top:
        return QIcon(pixmap)

    trimmed = pixmap.copy(left, top, right - left + 1, bottom - top + 1)
    if padding <= 0:
        return QIcon(trimmed)

    padded = QPixmap(trimmed.width() + padding * 2, trimmed.height() + padding * 2)
    padded.fill(Qt.transparent)
    painter = QPainter(padded)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.drawPixmap(padding, padding, trimmed)
    painter.end()
    return QIcon(padded)


def entries_word(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return 'запись'
    if count % 10 in (2, 3, 4) and count % 100 not in (12, 13, 14):
        return 'записи'
    return 'записей'
