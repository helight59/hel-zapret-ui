from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from src.app.config import AppConfig
from src.cli.process import run


log = logging.getLogger('windows.autostart')

_TASK_NAME = 'hel_zapret_ui_autostart'


@dataclass
class AutostartSyncResult:
    ok: bool
    enabled: bool
    changed: bool
    message: str = ''


def sync_autostart(cfg: AppConfig) -> AutostartSyncResult:
    enabled = bool(getattr(cfg, 'autostart_enabled', True))
    if sys.platform != 'win32':
        return AutostartSyncResult(True, enabled, False, '')

    try:
        exists = is_autostart_enabled()
        if enabled and exists:
            return AutostartSyncResult(True, True, False, '')
        if (not enabled) and (not exists):
            return AutostartSyncResult(True, False, False, '')
        if enabled:
            _register_task()
            return AutostartSyncResult(True, True, True, '')
        _unregister_task()
        return AutostartSyncResult(True, False, True, '')
    except Exception as exc:
        log.exception('autostart sync failed')
        return AutostartSyncResult(False, enabled, False, str(exc))


def is_autostart_enabled() -> bool:
    if sys.platform != 'win32':
        return False
    script = _ps_get_exists_script()
    result = run(['powershell.exe', '-NoProfile', '-Command', script], timeout=20)
    if result.code != 0:
        txt = (result.out or '') + '\n' + (result.err or '')
        if 'cannot find any task' in txt.lower():
            return False
    return (result.out or '').strip().lower() == 'true'


def _register_task() -> None:
    execute, arguments, working_dir = _build_launch_parts()
    script = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        f"$taskName = '{_ps_quote(_TASK_NAME)}'",
        f"$execute = '{_ps_quote(execute)}'",
        f"$arguments = '{_ps_quote(arguments)}'",
        f"$workingDir = '{_ps_quote(working_dir)}'",
        "$userId = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name",
        "$action = New-ScheduledTaskAction -Execute $execute -Argument $arguments -WorkingDirectory $workingDir",
        "$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userId",
        "$principal = New-ScheduledTaskPrincipal -UserId $userId -LogonType InteractiveToken -RunLevel Highest",
        "$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances Ignore",
        "Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force | Out-Null",
    ])
    result = run(['powershell.exe', '-NoProfile', '-Command', script], timeout=30)
    if result.code != 0:
        raise RuntimeError((result.err or result.out or 'Не удалось включить автозапуск').strip())
    log.info('autostart task registered name=%s execute=%s', _TASK_NAME, execute)


def _unregister_task() -> None:
    script = "\n".join([
        "$ErrorActionPreference = 'Stop'",
        f"$taskName = '{_ps_quote(_TASK_NAME)}'",
        "Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue | Out-Null",
    ])
    result = run(['powershell.exe', '-NoProfile', '-Command', script], timeout=20)
    if result.code != 0:
        raise RuntimeError((result.err or result.out or 'Не удалось выключить автозапуск').strip())
    log.info('autostart task removed name=%s', _TASK_NAME)


def _build_launch_parts() -> tuple[str, str, str]:
    if getattr(sys, 'frozen', False):
        exe = Path(sys.executable).resolve()
        return str(exe), '--start-hidden', str(exe.parent)

    python_exe = Path(sys.executable).resolve()
    pythonw_exe = python_exe.with_name('pythonw.exe')
    if pythonw_exe.exists():
        python_exe = pythonw_exe
    workdir = Path(__file__).resolve().parents[3]
    return str(python_exe), '-m src.main --start-hidden', str(workdir)


def _ps_get_exists_script() -> str:
    return "\n".join([
        "$task = Get-ScheduledTask -TaskName '" + _ps_quote(_TASK_NAME) + "' -ErrorAction SilentlyContinue",
        "if ($null -ne $task) { 'True' } else { 'False' }",
    ])


def _ps_quote(value: str) -> str:
    return str(value).replace("'", "''")
