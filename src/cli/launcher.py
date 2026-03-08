import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from src.services.windows.tasks import is_process_running
from src.cli.bat_cmdline import extract_winws_args_from_bat_text, expand_bat_vars, split_windows_cmdline

CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008

@dataclass
class LaunchResult:
    ok: bool
    message: str

def start_winws_from_bat(zapret_root: Path, bat_name: str) -> LaunchResult:
    bat_path = zapret_root / bat_name
    winws = zapret_root / 'bin' / 'winws.exe'
    if not bat_path.exists():
        return LaunchResult(False, 'bat not found')
    if not winws.exists():
        return LaunchResult(False, 'winws.exe not found')
    text = bat_path.read_text(encoding='utf-8', errors='ignore')
    args = extract_winws_args_from_bat_text(text)
    if not args:
        return LaunchResult(False, 'winws args not found in bat')
    args = expand_bat_vars(args, zapret_root)
    argv = split_windows_cmdline(args)
    try:
        subprocess.Popen(
            [str(winws), *argv],
            cwd=str(zapret_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
            close_fds=True,
        )
    except Exception as e:
        return LaunchResult(False, str(e))
    time.sleep(0.4)
    if is_process_running('winws.exe'):
        return LaunchResult(True, 'winws started')
    return LaunchResult(False, 'winws did not start')