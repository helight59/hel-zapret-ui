from PySide6.QtGui import QIcon
from src.utils.paths import bundle_dir

def app_icon() -> QIcon:
    p = bundle_dir() / 'assets' / 'app.ico'
    if p.exists():
        return QIcon(str(p))
    p = bundle_dir() / 'assets' / 'app.png'
    if p.exists():
        return QIcon(str(p))
    return QIcon()
