from __future__ import annotations

from PySide6.QtWidgets import QProgressBar, QVBoxLayout, QWidget

from src.ui.components.design_tokens import TOKENS


class BusyStrip(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 1, 0, 1)
        layout.setSpacing(0)

        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(TOKENS.busy_indicator_height)
        self.bar.setVisible(False)
        layout.addWidget(self.bar)

        self.setFixedHeight(TOKENS.busy_strip_height)

    def set_busy(self, busy: bool) -> None:
        self.bar.setVisible(bool(busy))
