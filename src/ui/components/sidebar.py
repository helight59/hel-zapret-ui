from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEasingCurve, Property, QPropertyAnimation, QSize, Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QLayout, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from src.ui.components.design_tokens import TOKENS


def _repolish(w: QWidget) -> None:
    st = w.style()
    st.unpolish(w)
    st.polish(w)
    w.update()


class _NavButton(QPushButton):
    def __init__(self, text: str, icon: QIcon | None = None):
        super().__init__(text)
        self._full_text = text
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty('navBtn', True)
        if icon is not None:
            self.setIcon(icon)
            self.setIconSize(QSize(20, 20))

    def set_collapsed(self, collapsed: bool) -> None:
        if collapsed:
            self.setText('')
            self.setToolTip(self._full_text)
        else:
            self.setText(self._full_text)
            self.setToolTip('')
        self.setProperty('iconOnly', collapsed)
        _repolish(self)


class _SubNavButton(QPushButton):
    def __init__(self, text: str):
        super().__init__(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty('subNavBtn', True)




class _ToggleRow(QWidget):
    def __init__(self, button: QPushButton):
        super().__init__()
        self._button = button
        self._button.setParent(self)
        self._progress = 1.0
        self.setFixedHeight(TOKENS.control_height_m)

    def set_progress(self, progress: float) -> None:
        self._progress = max(0.0, min(1.0, float(progress)))
        self._update_button_pos()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_button_pos()

    def _update_button_pos(self) -> None:
        btn_w = self._button.width() or self._button.sizeHint().width()
        btn_h = self._button.height() or self._button.sizeHint().height()
        x_center = max(0, round((self.width() - btn_w) / 2))
        x_right = max(0, self.width() - btn_w)
        x = round(x_center + (x_right - x_center) * self._progress)
        y = max(0, round((self.height() - btn_h) / 2))
        self._button.move(x, y)


class _GroupHeader(QWidget):
    def __init__(self, text: str, icon: QIcon | None = None):
        super().__init__()
        self.setProperty('groupHeader', True)

        row = QHBoxLayout(self)
        row.setContentsMargins(TOKENS.space_m, TOKENS.space_s, TOKENS.space_m, TOKENS.space_s)
        row.setSpacing(TOKENS.space_m)

        self.icon = QLabel('')
        self.icon.setFixedSize(22, 22)
        if icon is not None:
            self.icon.setPixmap(icon.pixmap(22, 22))
        row.addWidget(self.icon)

        self.title = QLabel(text)
        self.title.setProperty('groupTitle', True)
        row.addWidget(self.title, 1)

    def set_collapsed(self, collapsed: bool) -> None:
        self.title.setVisible(not collapsed)

    def set_active(self, active: bool) -> None:
        self.setProperty('active', active)
        _repolish(self)


class Sidebar(QFrame):
    routeSelected = Signal(str)
    exitRequested = Signal()

    def __init__(self, assets_dir: Path):
        super().__init__()
        self.setProperty('sidebar', True)
        self.setFrameShape(QFrame.NoFrame)

        self._assets = assets_dir
        self._collapsed = False
        self._w_open = TOKENS.sidebar_open_width
        self._w_closed = TOKENS.sidebar_closed_width

        self._sidebar_width = self._w_open

        self._anim = QPropertyAnimation(self, b'sidebarWidth')
        self._anim.setDuration(180)
        self._anim.setEasingCurve(QEasingCurve.InOutCubic)

        self.btnToggle = QPushButton('')
        self.btnToggle.setCursor(Qt.PointingHandCursor)
        self.btnToggle.setProperty('sidebarToggle', True)
        self.btnToggle.setIcon(self._icon('sidebar.png'))
        self.btnToggle.setIconSize(QSize(18, 18))
        self.btnToggle.setFixedSize(TOKENS.control_height_m, TOKENS.control_height_m)
        self.btnToggle.clicked.connect(self.toggle)
        self._toggle_row = _ToggleRow(self.btnToggle)

        self.btnHome = _NavButton('Главная', self._icon('main.png'))
        self.btnTests = _NavButton('Тесты соединения', self._icon('test.png'))
        self.btnAbout = _NavButton('О приложении', self._icon('about.png'))

        self.btnSettings = _NavButton('Настройки', self._icon('setting.png'))
        self.subSettings = QWidget()
        self._sub_layout = QVBoxLayout(self.subSettings)
        self._sub_layout.setContentsMargins(0, 0, 0, 0)
        self._sub_layout.setSpacing(TOKENS.space_xs)
        self._sub_layout.setAlignment(Qt.AlignTop)
        self._sub_layout.setSizeConstraint(QLayout.SetMinimumSize)
        self.subSettings.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.btnSettingsApp = _SubNavButton('Приложение')
        self.btnSettingsZapret = _SubNavButton('Zapret')
        self.btnSettingsLists = _SubNavButton('Списки')
        for b in (self.btnSettingsApp, self.btnSettingsZapret, self.btnSettingsLists):
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self._sub_layout.addWidget(b)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for b in (self.btnHome, self.btnTests, self.btnAbout, self.btnSettingsApp, self.btnSettingsZapret, self.btnSettingsLists):
            self._group.addButton(b)

        self._route_to_btn: dict[str, QPushButton] = {
            'home': self.btnHome,
            'tests': self.btnTests,
            'settings_app': self.btnSettingsApp,
            'settings_zapret': self.btnSettingsZapret,
            'settings_lists': self.btnSettingsLists,
            'about': self.btnAbout,
        }

        self.btnHome.clicked.connect(lambda: self.routeSelected.emit('home'))
        self.btnTests.clicked.connect(lambda: self.routeSelected.emit('tests'))
        self.btnAbout.clicked.connect(lambda: self.routeSelected.emit('about'))
        self.btnSettings.clicked.connect(lambda: self.routeSelected.emit('settings_app'))
        self.btnSettingsApp.clicked.connect(lambda: self.routeSelected.emit('settings_app'))
        self.btnSettingsZapret.clicked.connect(lambda: self.routeSelected.emit('settings_zapret'))
        self.btnSettingsLists.clicked.connect(lambda: self.routeSelected.emit('settings_lists'))

        self.btnExit = _NavButton('Выход', self._icon('exit.png'))
        self.btnExit.setCheckable(False)
        self.btnExit.clicked.connect(self.exitRequested.emit)

        self._root_layout = QVBoxLayout(self)
        self._root_layout.setContentsMargins(TOKENS.space_m, TOKENS.space_m, TOKENS.space_m, TOKENS.space_m)
        self._root_layout.setSpacing(0)

        self._root_layout.addWidget(self._toggle_row)
        self._root_layout.addSpacing(TOKENS.space_m)

        self._nav_layout = QVBoxLayout()
        self._nav_layout.setContentsMargins(0, 0, 0, 0)
        self._nav_layout.setSpacing(TOKENS.space_xs)
        self._nav_layout.setAlignment(Qt.AlignTop)
        self._nav_layout.addWidget(self.btnHome)
        self._nav_layout.addWidget(self.btnTests)
        self._nav_layout.addSpacing(2)
        self._nav_layout.addWidget(self.btnSettings)
        self._nav_layout.addWidget(self.subSettings)
        self._nav_layout.addSpacing(2)
        self._nav_layout.addWidget(self.btnAbout)
        self._root_layout.addLayout(self._nav_layout, 1)
        self._root_layout.addSpacing(TOKENS.space_xs)
        self._root_layout.addWidget(self.btnExit)

        self.setFixedWidth(self._w_open)
        self._locked = False
        self._update_sidebar_chrome(self._w_open)

    def set_locked(self, locked: bool) -> None:
        self._locked = bool(locked)
        for b in (self.btnHome, self.btnTests, self.btnSettings, self.btnAbout, self.btnSettingsApp, self.btnSettingsZapret, self.btnSettingsLists):
            b.setEnabled(not self._locked)

    def _get_sidebar_width(self) -> int:
        return int(self._sidebar_width)

    def _set_sidebar_width(self, w: int) -> None:
        self._sidebar_width = int(w)
        self.setFixedWidth(int(w))
        self._update_sidebar_chrome(int(w))

    sidebarWidth = Property(int, _get_sidebar_width, _set_sidebar_width)



    def _collapse_progress(self, width: int | None = None) -> float:
        current = int(self.width() if width is None else width)
        span = max(1, self._w_open - self._w_closed)
        progress = (current - self._w_closed) / span
        return max(0.0, min(1.0, progress))

    def _update_sidebar_chrome(self, width: int | None = None) -> None:
        progress = self._collapse_progress(width)
        side_margin = round(TOKENS.space_s + (TOKENS.space_m - TOKENS.space_s) * progress)
        self._root_layout.setContentsMargins(side_margin, TOKENS.space_m, side_margin, TOKENS.space_m)
        self._toggle_row.set_progress(progress)

    def _icon(self, name: str) -> QIcon:
        return QIcon(str((self._assets / name).resolve()))

    def toggle(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed

        try:
            self._anim.finished.disconnect(self._after_collapse)
        except Exception:
            pass
        try:
            self._anim.finished.disconnect(self._after_expand)
        except Exception:
            pass

        if collapsed:
            self._anim.stop()
            self._anim.setStartValue(int(self.width()))
            self._anim.setEndValue(self._w_closed)
            self._anim.finished.connect(self._after_collapse)
            self._anim.start()
            return

        # Restore text BEFORE the expand animation so it behaves like overflow:hidden.
        # Text should be clipped by width while expanding, not appear suddenly at the end.
        self.btnHome.set_collapsed(False)
        self.btnTests.set_collapsed(False)
        self.btnSettings.set_collapsed(False)
        self.btnAbout.set_collapsed(False)
        self.btnExit.set_collapsed(False)

        self._anim.stop()
        self._anim.setStartValue(int(self.width()))
        self._anim.setEndValue(self._w_open)
        self._anim.finished.connect(self._after_expand)
        self._anim.start()

    def _after_collapse(self) -> None:
        try:
            self._anim.finished.disconnect(self._after_collapse)
        except Exception:
            pass
        self.btnHome.set_collapsed(True)
        self.btnTests.set_collapsed(True)
        self.btnSettings.set_collapsed(True)
        self.btnAbout.set_collapsed(True)
        self.btnExit.set_collapsed(True)
        self.subSettings.setVisible(False)

    def _after_expand(self) -> None:
        try:
            self._anim.finished.disconnect(self._after_expand)
        except Exception:
            pass
        self.subSettings.setVisible(True)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_sidebar_chrome()

    def set_route(self, route: str) -> None:
        b = self._route_to_btn.get(route)
        if b is not None:
            b.setChecked(True)
        self.btnSettings.setChecked(route in ('settings_app', 'settings_zapret', 'settings_lists'))
        if self._collapsed:
            self.subSettings.setVisible(False)
