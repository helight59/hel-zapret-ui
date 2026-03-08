import ctypes
import os
import sys
from pathlib import Path

def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def ensure_elevated() -> None:
    if os.name != 'nt':
        return
    if is_admin():
        return

    exe = sys.executable

    if getattr(sys, 'frozen', False):
        params = ' '.join([_quote(a) for a in sys.argv])
    else:
        params = '-m src.main'
        extra = sys.argv[1:]
        if extra:
            params += ' ' + ' '.join(_quote(a) for a in extra)

    try:
        ctypes.windll.shell32.ShellExecuteW(None, 'runas', exe, params, str(Path.cwd()), 1)
    except Exception:
        return
    raise SystemExit(0)

def _quote(s: str) -> str:
    if not s:
        return '""'
    if any(c in s for c in ' \t"'):
        return '"' + s.replace('"', '\\"') + '"'
    return s