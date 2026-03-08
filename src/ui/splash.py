from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel

from src.ui.components import Card, Spinner, TOKENS


class SplashWindow(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet('QDialog { background: transparent; }')
        self.setModal(False)
        self.setFixedSize(360, 220)

        root = QVBoxLayout(self)
        root.setContentsMargins(TOKENS.space_xl, TOKENS.space_xl, TOKENS.space_xl, TOKENS.space_xl)
        root.setSpacing(0)

        card = Card('')
        root.addWidget(card)

        v = card.body
        v.setSpacing(TOKENS.space_m)
        v.addStretch(1)
        self.spinner = Spinner(46)
        v.addWidget(self.spinner, 0, Qt.AlignHCenter)
        self.title = QLabel('hel zapret ui')
        f = self.title.font()
        f.setBold(True)
        self.title.setFont(f)
        v.addWidget(self.title, 0, Qt.AlignHCenter)
        self.subtitle = QLabel('Проверяем статус…')
        self.subtitle.setProperty('muted', True)
        v.addWidget(self.subtitle, 0, Qt.AlignHCenter)
        v.addStretch(1)

        self._center()

    def set_subtitle(self, text: str) -> None:
        self.subtitle.setText((text or '').strip() or 'Загрузка…')

    def _center(self) -> None:
        scr = QGuiApplication.primaryScreen()
        if not scr:
            return
        g = scr.availableGeometry()
        self.move(g.center().x() - int(self.width() / 2), g.center().y() - int(self.height() / 2))
