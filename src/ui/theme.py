from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QApplication, QProxyStyle, QStyle

from src.ui.components.design_tokens import TOKENS


class VkStyle(QProxyStyle):
    def pixelMetric(self, metric, option=None, widget=None):
        if metric in (QStyle.PM_IndicatorWidth, QStyle.PM_IndicatorHeight):
            return 18
        return super().pixelMetric(metric, option, widget)

    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PE_IndicatorArrowDown:
            if painter:
                rect = option.rect
                painter.save()
                disabled = not bool(option.state & QStyle.State_Enabled)
                color = QColor(TOKENS.text_disabled if disabled else TOKENS.text_muted)
                painter.setRenderHint(QPainter.Antialiasing, True)
                painter.setPen(Qt.NoPen)
                painter.setBrush(color)

                width = float(rect.width())
                height = float(rect.height())
                size = max(6.0, min(width, height) * 0.55)
                cx = float(rect.center().x())
                cy = float(rect.center().y())
                poly = QPolygonF([
                    QPointF(cx - size * 0.55, cy - size * 0.18),
                    QPointF(cx + size * 0.55, cy - size * 0.18),
                    QPointF(cx, cy + size * 0.45),
                ])
                painter.drawPolygon(poly)
                painter.restore()
                return

        if element == QStyle.PE_IndicatorCheckBox:
            if painter:
                rect = option.rect
                painter.save()
                painter.setRenderHint(QPainter.Antialiasing, True)

                enabled = bool(option.state & QStyle.State_Enabled)
                checked = bool(option.state & QStyle.State_On)

                border = QColor(TOKENS.border if enabled else TOKENS.border_soft)
                fill = QColor(TOKENS.panel_bg if enabled else TOKENS.panel_bg_soft)
                if checked:
                    border = QColor(TOKENS.primary if enabled else '#cfd8e3')
                    fill = QColor(TOKENS.primary if enabled else '#cfd8e3')

                painter.setPen(QPen(border, 1))
                painter.setBrush(fill)
                painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4.0, 4.0)

                if checked:
                    pen = QPen(QColor('#ffffff'), 2.2)
                    pen.setCapStyle(Qt.RoundCap)
                    pen.setJoinStyle(Qt.RoundJoin)
                    painter.setPen(pen)

                    x = rect.x()
                    y = rect.y()
                    width = rect.width()
                    height = rect.height()

                    x1 = x + int(width * 0.28)
                    y1 = y + int(height * 0.55)
                    x2 = x + int(width * 0.44)
                    y2 = y + int(height * 0.70)
                    x3 = x + int(width * 0.74)
                    y3 = y + int(height * 0.32)
                    painter.drawLine(x1, y1, x2, y2)
                    painter.drawLine(x2, y2, x3, y3)

                painter.restore()
                return

        super().drawPrimitive(element, option, painter, widget)


def apply_theme(app: QApplication) -> None:
    app.setStyle(VkStyle(app.style()))
    app.setStyleSheet(_qss())


def _qss() -> str:
    return f"""
QMainWindow {{ background: {TOKENS.app_bg}; }}
QWidget {{ color: {TOKENS.text_primary}; font-size: {TOKENS.font_size_base}px; }}
QLabel[muted="true"] {{ color: {TOKENS.text_muted}; }}
QLabel[dangerText="true"] {{ color: {TOKENS.danger}; }}
QLabel[warningText="true"] {{ color: {TOKENS.warning}; font-size: {TOKENS.font_size_sm}px; font-weight: 600; }}
QLabel[pageTitle="true"] {{ font-size: {TOKENS.font_size_title}px; font-weight: 700; }}
QLabel[cardTitle="true"] {{ font-size: {TOKENS.font_size_base + 1}px; font-weight: 700; }}

QTabWidget::pane {{ border: 0; }}
QTabBar::tab {{
  background: transparent;
  padding: {TOKENS.space_s}px {TOKENS.space_m}px;
  margin: {TOKENS.space_xs}px;
  border-radius: {TOKENS.radius_s}px;
}}
QTabBar::tab:selected {{ background: {TOKENS.panel_bg}; }}
QTabBar::tab:hover {{ background: {TOKENS.panel_bg_active}; }}

QWidget[sidebar="true"] {{
  background: {TOKENS.panel_bg};
  border: 1px solid {TOKENS.border_soft};
  border-radius: {TOKENS.radius_m}px;
}}

QPushButton[sidebarToggle="true"] {{
  background: transparent;
  border: 0;
  border-radius: {TOKENS.radius_s}px;
  padding: 0 {TOKENS.space_s}px;
  min-height: {TOKENS.control_height_m}px;
  max-height: {TOKENS.control_height_m}px;
}}
QPushButton[sidebarToggle="true"]:hover {{ background: {TOKENS.panel_bg_soft}; }}
QPushButton[sidebarToggle="true"]:pressed {{ background: {TOKENS.panel_bg_active}; }}
QPushButton[sidebarToggle="true"]:disabled {{ background: transparent; }}

QPushButton[navBtn="true"] {{
  background: transparent;
  border: 0;
  border-radius: {TOKENS.radius_s}px;
  padding: 0 {TOKENS.space_m}px;
  text-align: left;
  color: {TOKENS.text_primary};
  min-height: {TOKENS.control_height_m}px;
  max-height: {TOKENS.control_height_m}px;
}}
QPushButton[navBtn="true"]:hover {{ background: {TOKENS.panel_bg_soft}; }}
QPushButton[navBtn="true"]:checked {{ background: {TOKENS.panel_bg_active}; }}
QPushButton[navBtn="true"]:disabled {{ background: transparent; color: {TOKENS.text_disabled}; }}
QPushButton[navBtn="true"]:checked:disabled {{ background: {TOKENS.panel_bg_soft}; color: {TOKENS.text_disabled}; }}
QPushButton[navBtn="true"][iconOnly="true"] {{ padding: 0; text-align: center; }}

QPushButton[subNavBtn="true"] {{
  background: transparent;
  border: 0;
  border-radius: {TOKENS.radius_s}px;
  padding: 0 {TOKENS.space_m}px 0 {TOKENS.space_xl + TOKENS.space_m}px;
  text-align: left;
  font-size: {TOKENS.font_size_sm}px;
  color: {TOKENS.text_primary};
  min-height: {TOKENS.control_height_s}px;
  max-height: {TOKENS.control_height_s}px;
}}
QPushButton[subNavBtn="true"]:hover {{ background: {TOKENS.panel_bg_soft}; }}
QPushButton[subNavBtn="true"]:checked {{ background: {TOKENS.panel_bg_active}; }}
QPushButton[subNavBtn="true"]:disabled {{ background: transparent; color: {TOKENS.text_disabled}; }}
QPushButton[subNavBtn="true"]:checked:disabled {{ background: {TOKENS.panel_bg_soft}; color: {TOKENS.text_disabled}; }}

QWidget[groupHeader="true"] {{ border-radius: {TOKENS.radius_s}px; }}
QWidget[groupHeader="true"][active="true"] {{ background: {TOKENS.panel_bg_active}; }}
QWidget[groupHeader="true"] QLabel[groupTitle="true"] {{ font-weight: 600; }}

QFrame[subMenuBar="true"] {{
  background: {TOKENS.panel_bg};
  border: 1px solid {TOKENS.border_soft};
  border-radius: {TOKENS.radius_m}px;
}}

QPushButton[subTopBtn="true"] {{
  background: transparent;
  border: 0;
  border-radius: {TOKENS.radius_s}px;
  padding: 0 {TOKENS.space_m}px;
  color: {TOKENS.text_primary};
  min-height: {TOKENS.control_height_m}px;
  max-height: {TOKENS.control_height_m}px;
}}
QPushButton[subTopBtn="true"]:hover {{ background: {TOKENS.panel_bg_soft}; }}
QPushButton[subTopBtn="true"]:checked {{ background: {TOKENS.panel_bg_active}; }}

QPushButton[anchorBtn="true"] {{
  background: transparent;
  border: 0;
  border-radius: {TOKENS.radius_s}px;
  padding: 0 {TOKENS.space_s + 2}px;
  text-align: left;
  color: {TOKENS.text_primary};
  min-height: {TOKENS.control_height_m}px;
  max-height: {TOKENS.control_height_m}px;
}}
QPushButton[anchorBtn="true"]:hover {{ background: {TOKENS.panel_bg_soft}; }}
QPushButton[anchorBtn="true"]:checked {{ background: transparent; }}

QPushButton[smallRoundButton="true"] {{
  background: {TOKENS.border_soft};
  color: {TOKENS.text_primary};
  border: 0;
  border-radius: {TOKENS.radius_round}px;
  padding: 0;
  min-width: {TOKENS.control_height_s}px;
  max-width: {TOKENS.control_height_s}px;
  min-height: {TOKENS.control_height_s}px;
  max-height: {TOKENS.control_height_s}px;
  qproperty-iconSize: 14px 14px;
}}
QPushButton[smallRoundButton="true"]:hover {{ background: {TOKENS.border}; }}
QPushButton[smallRoundButton="true"]:pressed {{ background: #d2dbe7; }}

QPushButton[listAddButton="true"] {{
  background: {TOKENS.panel_bg};
  border: 1px solid {TOKENS.border_soft};
  border-radius: {TOKENS.radius_m}px;
}}
QPushButton[listAddButton="true"]:hover {{ background: {TOKENS.panel_bg_soft}; border: 1px solid {TOKENS.border}; }}
QPushButton[listAddButton="true"]:pressed {{ background: {TOKENS.panel_bg_active}; border: 1px solid {TOKENS.border}; }}

QPushButton[rowAction="true"] {{
  background: transparent;
  border: 0;
  border-radius: {TOKENS.radius_s}px;
  padding: 0;
  min-width: {TOKENS.control_height_xs}px;
  max-width: {TOKENS.control_height_xs}px;
  min-height: {TOKENS.control_height_xs}px;
  max-height: {TOKENS.control_height_xs}px;
  qproperty-iconSize: 14px 14px;
}}
QPushButton[rowAction="true"]:hover {{ background: {TOKENS.panel_bg_hover}; }}
QPushButton[rowAction="true"]:pressed {{ background: {TOKENS.panel_bg_active}; }}

QFrame[listWrap="true"] {{
  background: transparent;
  border: 1px solid {TOKENS.border_soft};
  border-radius: 0;
}}
QFrame[listEntryRow="true"] {{
  background: {TOKENS.panel_bg};
  border-radius: 0;
}}
QFrame[listEntryRow="true"][alternateRow="true"] {{
  background: {TOKENS.panel_bg_soft};
}}
QLabel[listEntryText="true"] {{ padding: 0; }}

QFrame[card="true"] {{
  background: {TOKENS.panel_bg};
  border: 1px solid {TOKENS.border_soft};
  border-radius: {TOKENS.radius_m}px;
}}

QPushButton {{
  background: {TOKENS.primary};
  color: #ffffff;
  border: 0;
  border-radius: {TOKENS.radius_s}px;
  padding: 0 {TOKENS.space_m}px;
  min-height: {TOKENS.control_height_m}px;
  max-height: {TOKENS.control_height_m}px;
}}
QPushButton:hover {{ background: {TOKENS.primary_hover}; }}
QPushButton:pressed {{ background: {TOKENS.primary_pressed}; }}
QPushButton:disabled {{ background: #cfd8e3; color: {TOKENS.text_disabled}; }}

QPushButton[variant="secondary"] {{
  background: {TOKENS.border_soft};
  color: {TOKENS.text_primary};
}}
QPushButton[variant="secondary"]:hover {{ background: {TOKENS.border}; }}
QPushButton[variant="secondary"]:pressed {{ background: #d2dbe7; }}

QPushButton[variant="danger"] {{
  background: {TOKENS.danger};
  color: #ffffff;
}}
QPushButton[variant="danger"]:hover {{ background: {TOKENS.danger_hover}; }}
QPushButton[variant="danger"]:pressed {{ background: {TOKENS.danger_pressed}; }}

QComboBox, QLineEdit {{
  background: {TOKENS.panel_bg};
  border: 1px solid {TOKENS.border};
  border-radius: {TOKENS.radius_s}px;
  padding: 0 {TOKENS.space_m - 2}px;
  min-height: {TOKENS.control_height_l}px;
  max-height: {TOKENS.control_height_l}px;
}}
QComboBox:focus, QLineEdit:focus {{
  border: 1px solid {TOKENS.border_active};
}}
QComboBox::drop-down {{
  subcontrol-origin: padding;
  subcontrol-position: top right;
  width: 24px;
  border-left: 1px solid {TOKENS.border};
  border-top-right-radius: {TOKENS.radius_s}px;
  border-bottom-right-radius: {TOKENS.radius_s}px;
}}
QComboBox::drop-down:hover {{ background: {TOKENS.panel_bg_soft}; }}
QComboBox::down-arrow {{ width: 12px; height: 12px; }}
QComboBox:disabled, QLineEdit:disabled {{ background: {TOKENS.panel_bg_soft}; color: {TOKENS.text_disabled}; }}

QCheckBox {{ spacing: {TOKENS.space_m - 2}px; }}

QListWidget, QTableView {{
  background: {TOKENS.panel_bg};
  border: 1px solid {TOKENS.border};
  border-radius: {TOKENS.radius_m}px;
  gridline-color: {TOKENS.border_soft};
  alternate-background-color: {TOKENS.panel_bg_soft};
}}
QListWidget::item {{ padding: {TOKENS.space_s}px {TOKENS.space_m}px; border-radius: {TOKENS.radius_s}px; }}
QListWidget::item:hover {{ background: {TOKENS.panel_bg_soft}; }}
QHeaderView::section {{
  background: {TOKENS.panel_bg_soft};
  color: {TOKENS.text_primary};
  border: 0;
  border-bottom: 1px solid {TOKENS.border_soft};
  padding: {TOKENS.space_s}px {TOKENS.space_m - 2}px;
  font-weight: 600;
}}

QProgressBar {{
  border: 0;
  background: {TOKENS.border_soft};
  border-radius: 2px;
}}
QProgressBar::chunk {{
  background: {TOKENS.primary};
  border-radius: 2px;
}}

QScrollBar:vertical {{
  background: transparent;
  width: 10px;
  margin: 4px 2px 4px 2px;
}}
QScrollBar::handle:vertical {{
  background: #cfd8e3;
  min-height: 24px;
  border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{ background: #bcc7d4; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
  background: transparent;
  border: 0;
  height: 0;
}}
QScrollBar:horizontal {{
  background: transparent;
  height: 10px;
  margin: 2px 4px 2px 4px;
}}
QScrollBar::handle:horizontal {{
  background: #cfd8e3;
  min-width: 24px;
  border-radius: 5px;
}}
QScrollBar::handle:horizontal:hover {{ background: #bcc7d4; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
  background: transparent;
  border: 0;
  width: 0;
}}

QMenu, QDialog, QMessageBox {{
  background: {TOKENS.panel_bg};
  color: {TOKENS.text_primary};
}}
QMenu {{
  border: 1px solid {TOKENS.border};
  border-radius: {TOKENS.radius_m}px;
  padding: {TOKENS.space_s - 2}px;
}}
QMenu::item {{
  padding: {TOKENS.space_s - 2}px {TOKENS.space_m}px;
  border-radius: {TOKENS.radius_s}px;
}}
QMenu::item:selected {{ background: {TOKENS.panel_bg_active}; }}
QMenu::separator {{
  height: 1px;
  background: {TOKENS.border_soft};
  margin: {TOKENS.space_s - 2}px {TOKENS.space_s}px;
}}
"""
