import subprocess
import sys
from dataclasses import dataclass
from typing import Optional


def _win_hide_kwargs() -> dict:
    if not sys.platform.startswith('win'):
        return {}
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= getattr(subprocess, 'STARTF_USESHOWWINDOW', 1)
        si.wShowWindow = 0
        return {
            'startupinfo': si,
            'creationflags': getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000),
        }
    except Exception:
        return {'creationflags': 0x08000000}


def _oem_encoding_for(cmd0: str) -> str | None:
    if not sys.platform.startswith('win'):
        return None
    base = (cmd0 or '').strip().lower()
    if base.endswith('sc.exe') or base == 'sc.exe' or base.endswith('cmd.exe') or base == 'cmd.exe' or base.endswith('net.exe') or base == 'net.exe':
        try:
            import ctypes
            cp = int(ctypes.windll.kernel32.GetOEMCP())
            return f'cp{cp}'
        except Exception:
            return 'cp866'
    return None

@dataclass
class CmdResult:
    code: int
    out: str
    err: str

def run(cmd: list[str], cwd: Optional[str] = None, timeout: Optional[int] = None) -> CmdResult:
    enc = _oem_encoding_for(cmd[0] if cmd else '')
    p = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding=enc,
        errors='replace',
        timeout=timeout,
        shell=False,
        **_win_hide_kwargs(),
    )
    return CmdResult(p.returncode, p.stdout or '', p.stderr or '')

def popen_capture(cmd: list[str], cwd: Optional[str] = None) -> subprocess.Popen:
    enc = _oem_encoding_for(cmd[0] if cmd else '')
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding=enc,
        errors='replace',
        shell=False,
        **_win_hide_kwargs(),
    )