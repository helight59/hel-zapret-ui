from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QLabel, QVBoxLayout, QWidget

from src.ui.components.design_tokens import TOKENS


class Card(QFrame):
    def __init__(self, title: str = '', parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty('card', True)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(TOKENS.space_l, TOKENS.space_l, TOKENS.space_l, TOKENS.space_l)
        self._root.setSpacing(TOKENS.space_m)

        if title:
            lbl = QLabel(title)
            lbl.setProperty('cardTitle', True)
            self._root.addWidget(lbl)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(TOKENS.card_shadow_blur)
        shadow.setOffset(0, TOKENS.card_shadow_y)
        shadow.setColor(QColor(0, 0, 0, TOKENS.shadow_alpha))
        self.setGraphicsEffect(shadow)

    @property
    def body(self) -> QVBoxLayout:
        return self._root
