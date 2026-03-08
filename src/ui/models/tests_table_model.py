from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QBrush, QColor

BEST_STANDARD_ROLE = int(Qt.UserRole) + 1
BEST_DPI_ROLE = int(Qt.UserRole) + 2

_COLUMNS = [
    'Config',
    'Batch',
    'Now',
    'Standard',
    'Std HTTP',
    'Std Ping',
    'DPI',
    'DPI Suite',
    'Best',
]


def _status_color(s: str) -> QColor | None:
    v = (s or '').strip().upper()
    if v in {'OK', 'YES', 'ON'}:
        return QColor(205, 255, 205)
    if v in {'WARN', 'WARNING'}:
        return QColor(255, 248, 200)
    if v in {'FAIL', 'ERR', 'ERROR'}:
        return QColor(255, 210, 210)
    if v in {'RUNNING'}:
        return QColor(205, 235, 255)
    if v in {'QUEUED'}:
        return QColor(235, 235, 235)
    return None


def _counts_color(kind: str, s: str) -> QColor | None:
    v = (s or '').strip()
    if '/' not in v:
        return None

    parts = [p.strip() for p in v.split('/')]
    try:
        nums = [int(p) for p in parts]
    except Exception:
        return None

    k = (kind or '').strip().lower()
    if k == 'std_http':
        if len(nums) >= 3:
            ok, err, unsup = nums[0], nums[1], nums[2]
            if err > 0:
                return QColor(255, 210, 210)
            if unsup > 0:
                return QColor(255, 248, 200)
            if ok > 0:
                return QColor(205, 255, 205)
        return None

    if k == 'std_ping':
        if len(nums) >= 2:
            ok, fail = nums[0], nums[1]
            if fail > 0:
                return QColor(255, 248, 200)
            if ok > 0:
                return QColor(205, 255, 205)
        return None

    if k == 'dpi':
        if len(nums) >= 4:
            ok, fail, unsup, blocked = nums[0], nums[1], nums[2], nums[3]
            if blocked > 0:
                return QColor(255, 210, 210)
            if fail > 0:
                return QColor(255, 210, 210)
            if unsup > 0:
                return QColor(255, 248, 200)
            if ok > 0:
                return QColor(205, 255, 205)
        return None

    return None


def _best_text(best_standard: bool, best_dpi: bool) -> str:
    parts: list[str] = []
    if best_standard:
        parts.append('STD')
    if best_dpi:
        parts.append('DPI')
    return ', '.join(parts)


class TestsTableModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self.rows: list[dict] = []

    def set_rows(self, rows: list[dict]) -> None:
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def update_row(self, row: int, patch: dict) -> None:
        if row < 0 or row >= len(self.rows):
            return
        self.rows[row].update(patch)
        top_left = self.index(row, 0)
        bottom_right = self.index(row, self.columnCount() - 1)
        self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole, Qt.BackgroundRole, Qt.ForegroundRole])

    def rowCount(self, parent=QModelIndex()):
        return len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return len(_COLUMNS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return _COLUMNS[section]
        return str(section + 1)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        r = self.rows[index.row()]
        c = index.column()

        if role == Qt.DisplayRole:
            if c == 0:
                return r.get('name', '')
            if c == 1:
                return r.get('batch', '')
            if c == 2:
                return r.get('now', '')
            if c == 3:
                return r.get('standard', '')
            if c == 4:
                return r.get('std_http', '')
            if c == 5:
                return r.get('std_ping', '')
            if c == 6:
                return r.get('dpi', '')
            if c == 7:
                return r.get('dpi_suite', '')
            if c == 8:
                return _best_text(bool(r.get('best_standard')), bool(r.get('best_dpi')))
            return ''

        if c == 8 and role == BEST_STANDARD_ROLE:
            return bool(r.get('best_standard'))

        if c == 8 and role == BEST_DPI_ROLE:
            return bool(r.get('best_dpi'))

        if role == Qt.TextAlignmentRole:
            return int(Qt.AlignVCenter | (Qt.AlignLeft if c == 0 else Qt.AlignHCenter))

        if role == Qt.BackgroundRole:
            if c == 2:
                if (r.get('now') or '').strip():
                    return QBrush(QColor(205, 235, 255))
                return None

            if c in {3, 6}:
                col = _status_color(str(r.get('standard' if c == 3 else 'dpi', '')))
                return QBrush(col) if col else None

            if c == 4:
                col = _counts_color('std_http', str(r.get('std_http', '')))
                return QBrush(col) if col else None
            if c == 5:
                col = _counts_color('std_ping', str(r.get('std_ping', '')))
                return QBrush(col) if col else None
            if c == 7:
                col = _counts_color('dpi', str(r.get('dpi_suite', '')))
                return QBrush(col) if col else None

            if c == 8:
                if bool(r.get('best_standard')) or bool(r.get('best_dpi')):
                    return QBrush(QColor(225, 215, 255))

        return None
