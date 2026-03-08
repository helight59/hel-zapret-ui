from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from src.ui.components import Spinner, TOKENS


class InstallDialog(QDialog):
    def __init__(self, title: str, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle(title)
        root = QVBoxLayout(self)
        root.setContentsMargins(TOKENS.space_l + 2, TOKENS.space_l + 2, TOKENS.space_l + 2, TOKENS.space_l + 2)
        root.setSpacing(TOKENS.space_m)

        self.lbl = QLabel(text)
        self.lbl.setWordWrap(True)
        root.addWidget(self.lbl)

        spinner_row = QHBoxLayout()
        spinner_row.addStretch(1)
        self.spinner = Spinner(40)
        spinner_row.addWidget(self.spinner)
        spinner_row.addStretch(1)
        root.addLayout(spinner_row)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        self.btnCancel = QPushButton('Отмена')
        self.btnCancel.setProperty('variant', 'secondary')
        btn_row.addWidget(self.btnCancel)
        root.addLayout(btn_row)

    def set_text(self, text: str) -> None:
        self.lbl.setText((text or '').strip() or '...')
