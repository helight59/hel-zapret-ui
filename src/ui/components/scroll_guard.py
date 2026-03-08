from __future__ import annotations

from PySide6.QtCore import QObject, QEvent, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QAbstractScrollArea, QScrollBar, QWidget


class WheelScrollGuard(QObject):
    def __init__(self, area: QAbstractScrollArea):
        super().__init__(area)
        self._area = area

    def eventFilter(self, obj, event):
        if event.type() != QEvent.Type.Wheel:
            return super().eventFilter(obj, event)
        if not isinstance(event, QWheelEvent):
            return super().eventFilter(obj, event)
        return self._handle_wheel(event)

    def _handle_wheel(self, event: QWheelEvent) -> bool:
        bar = self._pick_scrollbar(event)
        if bar is None:
            event.accept()
            return True
        delta = self._delta(event, bar.orientation() == Qt.Vertical)
        if delta == 0:
            event.accept()
            return True
        bar.setValue(self._next_value(bar, delta))
        event.accept()
        return True

    def _pick_scrollbar(self, event: QWheelEvent) -> QScrollBar | None:
        vertical = self._area.verticalScrollBar()
        if self._is_scrollable(vertical):
            return vertical
        horizontal = self._area.horizontalScrollBar()
        if self._is_scrollable(horizontal):
            return horizontal
        if not event.pixelDelta().isNull() or not event.angleDelta().isNull():
            return vertical
        return None

    def _is_scrollable(self, bar: QScrollBar | None) -> bool:
        return bar is not None and bar.maximum() > bar.minimum()

    def _delta(self, event: QWheelEvent, is_vertical: bool) -> int:
        pixel = event.pixelDelta().y() if is_vertical else event.pixelDelta().x()
        if pixel:
            return -int(pixel)
        angle = event.angleDelta().y() if is_vertical else event.angleDelta().x()
        if not angle:
            return 0
        bar = self._area.verticalScrollBar() if is_vertical else self._area.horizontalScrollBar()
        step = bar.singleStep() if bar is not None else 0
        if step <= 0:
            step = 24
        return -int(angle / 120) * step * 3

    def _next_value(self, bar: QScrollBar, delta: int) -> int:
        value = bar.value() + delta
        return max(bar.minimum(), min(bar.maximum(), value))


def install_wheel_guard(area: QAbstractScrollArea, widget: QWidget | None = None) -> WheelScrollGuard:
    guard = WheelScrollGuard(area)
    target = widget or area.viewport()
    target.installEventFilter(guard)
    setattr(area, '_wheel_scroll_guard', guard)
    return guard
