from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from src.ui.components.design_tokens import TOKENS


class ToggleSwitch(QWidget):
    toggled = Signal(bool)

    def __init__(self):
        super().__init__()
        self._checked = False
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(34)
        self.setMinimumWidth(64)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, value: bool) -> None:
        if self._checked == value:
            return
        self._checked = value
        self.update()

    def mousePressEvent(self, event):
        if not self.isEnabled():
            return
        if event.button() == Qt.LeftButton:
            self._checked = not self._checked
            self.toggled.emit(self._checked)
            self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(0, 0, self.width(), self.height())
        bg = QColor(TOKENS.primary) if self._checked else QColor('#b8c0cc')
        if not self.isEnabled():
            bg = QColor('#cfd8e3')
        painter.setPen(Qt.NoPen)
        painter.setBrush(bg)
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)

        diameter = self.height() - 8
        knob_x = self.width() - diameter - 4 if self._checked else 4
        knob = QRectF(knob_x, 4, diameter, diameter)
        painter.setBrush(QColor('#ffffff'))
        painter.drawEllipse(knob)
        painter.end()
