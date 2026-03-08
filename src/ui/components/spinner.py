from __future__ import annotations

import math

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from src.ui.components.design_tokens import TOKENS


class Spinner(QWidget):
    def __init__(self, size: int = 44, parent: QWidget | None = None):
        super().__init__(parent)
        self._size = max(18, int(size))
        self._angle = 0
        self.setFixedSize(self._size, self._size)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(60)

    def _tick(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        width = self.width()
        height = self.height()
        cx = width / 2
        cy = height / 2
        radius = min(width, height) / 2

        dots = 12
        dot_radius = max(2.0, radius * 0.10)
        ring_radius = radius * 0.62

        base = QColor(TOKENS.primary)
        for i in range(dots):
            angle = self._angle + (i * (360 / dots))
            rad = math.radians(angle)
            x = cx + (ring_radius * math.cos(rad))
            y = cy + (ring_radius * math.sin(rad))
            alpha = int(40 + (215 * (i + 1) / dots))
            color = QColor(base)
            color.setAlpha(alpha)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(int(x - dot_radius), int(y - dot_radius), int(dot_radius * 2), int(dot_radius * 2))
