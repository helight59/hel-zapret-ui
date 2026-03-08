import logging
import re
import time
from pathlib import Path
from src.services.zapret.service_fix import ensure_service_config_readable
from src.cli.service_bat import clean_via_menu as _clean_via_menu
from src.cli.service_bat import install_service as _install_service
from src.cli.service_bat import remove_services as _remove_services
from src.cli.process import run

log = logging.getLogger('service_manager')

class ZapretServiceManager:
    def __init__(self, zapret_root: Path):
        self.root = zapret_root

    def query_state(self) -> str:
        cmd = "try { (Get-Service -Name zapret -ErrorAction Stop).Status } catch { 'NOT_INSTALLED' }"
        r = run(["powershell.exe", "-NoProfile", "-Command", cmd])
        s = (r.out or "").strip().upper()
        if not s:
            return "UNKNOWN"
        if s == "NOT_INSTALLED":
            return "NOT_INSTALLED"
        if s in ("RUNNING", "STOPPED", "PAUSED", "START_PENDING", "STOP_PENDING", "PAUSE_PENDING", "CONTINUE_PENDING"):
            return s
        return "UNKNOWN"

    def is_installed(self) -> bool:
        return self.query_state() != "NOT_INSTALLED"

    def is_running(self) -> bool:
        return self.query_state() == "RUNNING"

    def start(self) -> bool:
        r = run(["sc.exe", "start", "zapret"])
        return r.code == 0

    def stop(self) -> bool:
        r = run(["sc.exe", "stop", "zapret"])
        return r.code == 0

    def restart(self) -> bool:
        self.stop()
        return self.start()

    def status_text(self) -> str:
        st = self.query_state()
        if st == "RUNNING":
            return "RUNNING"
        if st == "STOPPED":
            return "STOPPED"
        if st == "NOT_INSTALLED":
            return "NOT INSTALLED"
        return st

    def install_via_service_bat(self, strategy_bat: str) -> tuple[bool, str]:
        r = _install_service(self.root, strategy_bat)
        if not r.ok:
            tail = (r.output or "").strip()
            if tail:
                return (False, r.message + "\n\n" + tail)
            return (False, r.message)

        ok_fix, msg_fix = ensure_service_config_readable('zapret', self.root)
        if ok_fix:
            return (True, (r.message + "\n" + msg_fix).strip())

        tail = (r.output or "").strip()
        extra = ("\n\n" + tail) if tail else ""
        return (False, ("служба установилась, но конфиг некорректный: " + msg_fix + extra).strip())

    def remove_via_service_bat(self) -> tuple[bool, str]:
        r = _remove_services(self.root, total_timeout_s=35.0)
        if r.ok:
            return (True, r.message)

        tail = (r.output or "").strip()
        msg = (r.message or '').strip()
        log.warning('remove via service.bat failed: %s', msg or 'unknown')

        ok2, msg2 = self.remove_direct()
        if ok2:
            return (True, ('service.bat: ' + (msg or 'fail') + '\nsc.exe: ok').strip())

        combined = ('service.bat: ' + (msg or 'fail') + '\nsc.exe: ' + (msg2 or 'fail')).strip()
        extra = ('\n\n' + tail) if tail else ''
        return (False, combined + extra)

    def remove_direct(self) -> tuple[bool, str]:
        try:
            st0 = self.query_state()
            if st0 == 'NOT_INSTALLED':
                return (True, 'already not installed')

            _ = run(['sc.exe', 'stop', 'zapret'])

            deadline = time.monotonic() + 12.0
            while time.monotonic() < deadline:
                st = self.query_state()
                if st in ('STOPPED', 'NOT_INSTALLED'):
                    break
                time.sleep(0.3)

            r = run(['sc.exe', 'delete', 'zapret'])
            ok = (r.code == 0)
            out = ((r.out or '') + '\n' + (r.err or '')).strip()

            if (not ok) and ('does not exist' in out.lower() or 'не существует' in out.lower()):
                ok = True

            deadline2 = time.monotonic() + 12.0
            while time.monotonic() < deadline2:
                if self.query_state() == 'NOT_INSTALLED':
                    return (True, 'deleted')
                time.sleep(0.35)

            if ok and self.query_state() == 'NOT_INSTALLED':
                return (True, 'deleted')

            return (False, out or 'sc delete failed')
        except Exception as e:
            return (False, str(e))

    def clean_via_service_bat(self) -> tuple[bool, str]:
        r = _clean_via_menu(self.root)
        if r.ok:
            return (True, r.message)
        tail = (r.output or "").strip()
        if tail:
            return (False, r.message + "\n\n" + tail)
        return (False, r.message)