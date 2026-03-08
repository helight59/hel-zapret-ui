from __future__ import annotations

import logging
import re
from pathlib import Path

from src.cli.launcher import start_winws_from_bat
from src.cli.service_bat import remove_services as menu_remove_services
from src.services.zapret.process_monitor import WinwsMonitor
from src.services.zapret.service import ZapretService
from src.services.zapret.service_manager import ZapretServiceManager
from src.services.zapret.strategy_detect import detect_current_strategy


log = logging.getLogger('tests')


class UpdateCheckGuard:
    def __init__(self, zapret_dir: Path):
        self.root = normalize_zapret_root(zapret_dir)
        self.flag = self.root / 'utils' / 'check_updates.enabled'
        self.tmp = self.root / 'utils' / 'check_updates.enabled.hel_zapret_ui_off'
        self._moved = False

    def disable(self) -> None:
        try:
            if self.flag.exists() and (not self.tmp.exists()):
                self.flag.rename(self.tmp)
                self._moved = True
                log.info('tests: disabled check_updates.enabled')
        except Exception:
            return

    def restore(self) -> None:
        try:
            if self._moved and self.tmp.exists() and (not self.flag.exists()):
                self.tmp.rename(self.flag)
                log.info('tests: restored check_updates.enabled')
        except Exception:
            return


def normalize_zapret_root(zapret_dir: Path) -> Path:
    root = Path(zapret_dir)
    if not (root / 'service.bat').exists() and (root / 'zapret' / 'service.bat').exists():
        return root / 'zapret'
    return root


def snapshot_zapret_state(zapret_dir: Path, data_dir: Path) -> dict[str, object]:
    service = ZapretService(zapret_dir, data_dir)
    status = service.status()
    installed = status.service_state != 'NOT_INSTALLED'
    service_running = status.service_state == 'RUNNING'
    capture_running = status.capture_running
    was_running = service_running or capture_running

    strategy = (status.current_strategy or '').strip()
    if not strategy:
        try:
            detected = detect_current_strategy(zapret_dir)
            strategy = (detected.strategy or '').strip()
        except Exception:
            strategy = ''

    service_path = ''
    try:
        cmd = "(Get-CimInstance Win32_Service -Filter \"Name='zapret'\" | Select-Object -First 1 -ExpandProperty PathName)"
        from src.cli.powershell import run_powershell
        service_path = (run_powershell(cmd) or '').strip()
    except Exception:
        service_path = ''

    our_winws = str((zapret_dir / 'bin' / 'winws.exe').resolve()).lower().replace('/', '\\')
    service_low = service_path.lower().replace('/', '\\')
    external = bool(service_low and 'winws.exe' in service_low and our_winws and (our_winws not in service_low))

    start_mode = 'auto'
    try:
        from src.cli.process import run
        result = run(['sc.exe', 'qc', 'zapret'])
        if result.code == 0 and result.out:
            match = re.search(r'(?im)^\s*START_TYPE\s*:\s*\d+\s+(\w+)', result.out)
            if match:
                found = (match.group(1) or '').strip().upper()
                if found == 'DEMAND_START':
                    start_mode = 'demand'
                elif found == 'DISABLED':
                    start_mode = 'disabled'
    except Exception:
        pass

    return {
        'installed': installed,
        'service_state': status.service_state,
        'service_running': service_running,
        'capture_running': capture_running,
        'was_running': was_running,
        'strategy': strategy,
        'svc_pathname': service_path,
        'external': external,
        'start_mode': start_mode,
    }


def remove_zapret_before_tests(zapret_dir: Path, data_dir: Path, snap: dict[str, object]) -> tuple[bool, str]:
    try:
        log.info('tests pre-remove: remove via service.bat')
        result = menu_remove_services(zapret_dir, total_timeout_s=180.0)
        log.info('tests pre-remove: done ok=%s msg="%s"', bool(result.ok), str(result.message or ''))
        if result.ok:
            return (True, '')
        low = (result.output or '').lower()
        if 'not installed' in low or 'does not exist' in low or 'не существует' in low:
            return (True, '')
        return (False, 'не удалось удалить службы zapret перед тестами: ' + (result.message or ''))
    except Exception as exc:
        return (False, str(exc))


def restore_zapret_after_tests(zapret_dir: Path, data_dir: Path, snap: dict[str, object]) -> dict[str, object]:
    installed = bool(snap.get('installed'))
    was_running = bool(snap.get('was_running'))
    strategy = (snap.get('strategy') or '') if isinstance(snap.get('strategy'), str) else ''
    external = bool(snap.get('external'))
    service_path = (snap.get('svc_pathname') or '') if isinstance(snap.get('svc_pathname'), str) else ''
    start_mode = (snap.get('start_mode') or 'auto') if isinstance(snap.get('start_mode'), str) else 'auto'

    result: dict[str, object] = {
        'ok': True,
        'message': '',
        'installed': installed,
        'was_running': was_running,
        'strategy': strategy,
        'external': external,
    }

    try:
        if installed:
            if external and service_path:
                ok, msg = restore_service_from_sc(service_path, start_mode)
                if not ok:
                    result['ok'] = False
                    result['message'] = msg
                    return result
            else:
                if not strategy:
                    result['ok'] = False
                    result['message'] = 'не удалось определить стратегию для восстановления службы'
                    return result
                manager = ZapretServiceManager(zapret_dir)
                ok, msg = manager.install_via_service_bat(strategy)
                if not ok:
                    result['ok'] = False
                    result['message'] = msg
                    return result

            manager = ZapretServiceManager(zapret_dir)
            if was_running:
                manager.start()
            else:
                manager.stop()
            return result

        if was_running and strategy:
            monitor = WinwsMonitor()
            if monitor.is_running():
                return result
            launch = start_winws_from_bat(zapret_dir, strategy)
            if not launch.ok:
                result['ok'] = False
                result['message'] = launch.message
            return result

        return result
    except Exception as exc:
        result['ok'] = False
        result['message'] = str(exc)
        return result


def restore_service_from_sc(bin_path: str, start_mode: str) -> tuple[bool, str]:
    from src.cli.process import run

    query = run(['sc.exe', 'query', 'zapret'])
    if query.code == 0:
        return (True, 'already exists')

    clean_path = (bin_path or '').strip()
    if not clean_path:
        return (False, 'empty service PathName')

    mode = (start_mode or 'auto').strip().lower()
    if mode not in ('auto', 'demand', 'disabled'):
        mode = 'auto'

    created = run(['sc.exe', 'create', 'zapret', f'binPath= {clean_path}', f'start= {mode}'])
    if created.code != 0:
        return (False, (created.out or '') + '\n' + (created.err or '') or 'sc create failed')
    return (True, 'restored')
