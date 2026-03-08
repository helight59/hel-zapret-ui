from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.services.updater.zapret_updater import ZapretUpdater
from src.services.zapret.cleanup import GoodbyeDpiDetection, detect_goodbyedpi, remove_goodbyedpi
from src.app.config import AppConfig
from src.services.zapret.detect_ps import get_winws_process_path, list_winws_services
from src.services.zapret.game_filter import write_game_filter_mode
from src.services.zapret.user_lists import sync_saved_user_lists
from src.cli.launcher import start_winws_from_bat
from src.services.zapret.layout import ZapretLayout
from src.services.zapret.process_monitor import WinwsMonitor
from src.services.zapret.service_manager import ZapretServiceManager
from src.services.zapret.strategy_detect import detect_current_strategy
from src.cli.process import run
from src.services.zapret.strategy_name import normalize_strategy_key


@dataclass
class ActionResult:
  ok: bool
  message: str


@dataclass
class ZapretStatus:
  service_state: str
  capture_running: bool
  current_strategy: str
  zapret_present: bool


@dataclass
class ZapretDiagnostics:
  service_state: str
  capture_running: bool
  winws_process_path: str
  our_winws_path: str
  winws_services: list[str]


class ZapretService:
  def __init__(self, zapret_dir: Path, data_dir: Path):
    self.zapret_dir = zapret_dir
    self.data_dir = data_dir

  def status(self) -> ZapretStatus:
    sm = ZapretServiceManager(self.zapret_dir)
    pm = WinwsMonitor()
    st = sm.query_state()
    cap = pm.is_running()

    cur = ''
    try:
      det = detect_current_strategy(self.zapret_dir)
      cur = det.strategy or ''
    except Exception:
      cur = ''

    present = (self.zapret_dir / 'bin' / 'winws.exe').exists()
    return ZapretStatus(
      service_state=st,
      capture_running=cap,
      current_strategy=cur,
      zapret_present=present,
    )

  def strategies(self) -> list[str]:
    lay = ZapretLayout(self.zapret_dir)
    return lay.list_strategies() if lay.ok() else []

  def set_enabled(self, on: bool, strategy_bat: str) -> ActionResult:
    return self.enable(on, strategy_bat)

  def enable(self, on: bool, strategy_bat: str) -> ActionResult:
    sm = ZapretServiceManager(self.zapret_dir)
    pm = WinwsMonitor()

    try:
      if on:
        self._sync_saved_app_settings()
        desired = (strategy_bat or '').strip()
        cur = ''
        try:
          cur = (self.status().current_strategy or '').strip()
        except Exception:
          cur = ''

        if sm.is_installed():
          if desired and (normalize_strategy_key(desired) != normalize_strategy_key(cur)):
            ir = self.install_service(desired)
            if not ir.ok:
              return ir

          stop_log = ''
          if sm.is_running():
            r_stop = run(['sc.exe', 'stop', 'zapret'])
            stop_log = (r_stop.out or '') + '\n' + (r_stop.err or '')
            _wait_service_state(sm, want='STOPPED', timeout_s=12.0)

          r_start = run(['sc.exe', 'start', 'zapret'])
          start_log = (r_start.out or '') + '\n' + (r_start.err or '')
          cmd_ok = r_start.code == 0
          ok = cmd_ok or _wait_service_state(sm, want='RUNNING', timeout_s=18.0)
          if ok:
            return ActionResult(True, 'включено')
          st = sm.query_state()
          q = run(['sc.exe', 'query', 'zapret'])
          qc = run(['sc.exe', 'qc', 'zapret'])
          details = _tail_text(stop_log + '\n\n' + start_log + '\n\n' + (q.out or '') + '\n' + (q.err or '') + '\n\n' + (qc.out or '') + '\n' + (qc.err or ''), 110)
          suffix = ('\n\n' + details) if details else ''
          return ActionResult(False, f'не удалось запустить службу (статус: {st})' + suffix)

        if not desired:
          return ActionResult(False, 'не выбрана стратегия')
        r = start_winws_from_bat(self.zapret_dir, desired)
        return ActionResult(r.ok, r.message)

      if sm.is_installed():
        sm.stop()
      pm.kill()
      return ActionResult(True, 'выключено')
    except Exception as e:
      return ActionResult(False, str(e))

  def apply_strategy(self, strategy_bat: str) -> ActionResult:
    desired = (strategy_bat or '').strip()
    if not desired:
      return ActionResult(False, 'не выбрана стратегия')

    sm = ZapretServiceManager(self.zapret_dir)
    pm = WinwsMonitor()

    try:
      self._sync_saved_app_settings()
      if sm.is_installed():
        ir = self.install_service(desired)
        if not ir.ok:
          return ir

        stop_log = ''
        if sm.is_running():
          r_stop = run(['sc.exe', 'stop', 'zapret'])
          stop_log = (r_stop.out or '') + '\n' + (r_stop.err or '')
          _wait_service_state(sm, want='STOPPED', timeout_s=12.0)

        r_start = run(['sc.exe', 'start', 'zapret'])
        start_log = (r_start.out or '') + '\n' + (r_start.err or '')
        cmd_ok = r_start.code == 0
        ok = cmd_ok or _wait_service_state(sm, want='RUNNING', timeout_s=18.0)
        if ok:
          return ActionResult(True, 'стратегия применена')
        st = sm.query_state()
        q = run(['sc.exe', 'query', 'zapret'])
        qc = run(['sc.exe', 'qc', 'zapret'])
        details = _tail_text(stop_log + '\n\n' + start_log + '\n\n' + (q.out or '') + '\n' + (q.err or '') + '\n\n' + (qc.out or '') + '\n' + (qc.err or ''), 110)
        suffix = ('\n\n' + details) if details else ''
        return ActionResult(False, f'стратегия применена, но служба не запустилась (статус: {st})' + suffix)

      if pm.is_running():
        pm.kill()
      r = start_winws_from_bat(self.zapret_dir, desired)
      return ActionResult(r.ok, 'стратегия применена' if r.ok else r.message)
    except Exception as e:
      return ActionResult(False, str(e))

  def install_or_update_zapret(
    self,
    version_tag: str = 'latest',
    on_progress: Callable[[int], None] | None = None,
    on_stage: Callable[[str], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
  ) -> ActionResult:
    def _guard_cancel():
      if cancel_check and cancel_check():
        raise RuntimeError('отменено')

    def _p(v: int):
      _guard_cancel()
      if on_progress:
        on_progress(v)

    def _s(t: str):
      _guard_cancel()
      if on_stage:
        on_stage(t)

    up = ZapretUpdater(self.zapret_dir, self.data_dir, self.data_dir / 'app.log')
    ok, msg = up.update(version_tag=version_tag, on_progress=_p, on_stage=_s)
    return ActionResult(ok, msg)

  def install_service(self, strategy_bat: str) -> ActionResult:
    self._sync_saved_app_settings()
    sm = ZapretServiceManager(self.zapret_dir)
    ok, msg = sm.install_via_service_bat(strategy_bat)
    return ActionResult(ok, msg)

  def restart(self, strategy_bat: str = '') -> ActionResult:
    st = self.status()
    desired = (strategy_bat or '').strip() or (st.current_strategy or '').strip()
    if not desired and ((st.service_state != 'NOT_INSTALLED') or st.capture_running):
      strategies = self.strategies()
      desired = strategies[0] if strategies else ''

    off = self.enable(False, '')
    if not off.ok:
      return off

    time.sleep(0.4)
    return self.enable(True, desired)

  def remove_services(self) -> ActionResult:
    sm = ZapretServiceManager(self.zapret_dir)
    pm = WinwsMonitor()
    ok, msg = sm.remove_via_service_bat()
    try:
      if pm.is_running():
        pm.kill()
    except Exception:
      pass
    return ActionResult(ok, msg)

  def goodbyedpi(self) -> GoodbyeDpiDetection:
    return detect_goodbyedpi()

  def remove_goodbyedpi(self):
    return remove_goodbyedpi()

  def _sync_saved_app_settings(self) -> None:
    try:
      cfg = AppConfig.load(self.data_dir)
      write_game_filter_mode(self.zapret_dir, cfg.game_filter_mode)
    except Exception:
      pass

    try:
      sync_saved_user_lists(self.zapret_dir, self.data_dir)
    except Exception:
      pass

  def diagnostics(self) -> ZapretDiagnostics:
    sm = ZapretServiceManager(self.zapret_dir)
    pm = WinwsMonitor()
    st = sm.query_state()
    cap = pm.is_running()
    wp = get_winws_process_path() if cap else ''
    our = str((self.zapret_dir / 'bin' / 'winws.exe').resolve()) if (self.zapret_dir / 'bin' / 'winws.exe').exists() else '-'
    svcs = list_winws_services()
    svc_lines: list[str] = []
    for s in svcs[:8]:
      svc_lines.append(f'{s.name} [{s.state}] {s.path}')
    return ZapretDiagnostics(
      service_state=st,
      capture_running=cap,
      winws_process_path=wp,
      our_winws_path=our,
      winws_services=svc_lines,
    )



def _wait_service_state(sm: ZapretServiceManager, want: str, timeout_s: float = 12.0, step_s: float = 0.4) -> bool:
  deadline = time.monotonic() + max(0.0, float(timeout_s))
  target = (want or '').strip().upper()
  while time.monotonic() < deadline:
    st = (sm.query_state() or '').strip().upper()
    if st == target:
      return True
    if target == 'RUNNING' and st in ('RUNNING', 'START_PENDING'):
      return True
    if target == 'STOPPED' and st in ('STOPPED', 'STOP_PENDING'):
      return True
    time.sleep(max(0.05, float(step_s)))
  st = (sm.query_state() or '').strip().upper()
  if target == 'RUNNING':
    return st in ('RUNNING', 'START_PENDING')
  if target == 'STOPPED':
    return st in ('STOPPED', 'STOP_PENDING')
  return st == target


def _tail_text(text: str, max_lines: int = 60) -> str:
  t = (text or '').replace('\r', '').strip('\n')
  if not t:
    return ''
  lines = t.split('\n')
  tail = lines[-max_lines:] if len(lines) > max_lines else lines
  return '\n'.join(tail).strip()
