import sys
from pathlib import Path


def app_dir() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def bundle_dir() -> Path:
    if getattr(sys, 'frozen', False):
        meipass = getattr(sys, '_MEIPASS', None)
        if isinstance(meipass, str) and meipass:
            return Path(meipass)
        return app_dir()
    return app_dir()
