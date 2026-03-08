from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import time

from src.app.config import AppConfig
from src.services.zapret.detect_ps import get_winws_process_path, list_winws_services
from src.services.zapret.game_filter import clear_runtime_game_filter_override, set_runtime_game_filter_override
from src.services.zapret.game_filter_state import read_game_filter_state
from src.services.zapret.service import ZapretService
from src.services.zapret.strategy_name import normalize_strategy_key


@dataclass
class HomeState:
    zapret_present: bool
    service_state: str
    capture_running: bool
    enabled: bool
    current_strategy: str
    selected_strategy: str
    strategies: list[str]
    external_present: bool
    external_hint: str
    show_install_zapret: bool
    show_strategy_select: bool
    show_apply_strategy: bool
    show_remove_goodbyedpi: bool
    warnings: list[str]
    runtime_game_filter_mode: str


class ServiceController:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg

    def build_state(self, selected_strategy: str = '') -> HomeState:
        service = self._service()
        status = service.status()
        strategies = service.strategies() if status.zapret_present else []

        current_strategy = (status.current_strategy or '').strip()
        selected = self._resolve_selected_strategy(selected_strategy, current_strategy, strategies)
        self.cfg.last_strategy = selected

        enabled = _status_is_enabled(status)
        game_filter_state = read_game_filter_state(
            self.cfg.zapret_dir,
            self.cfg.data_dir,
            self.cfg,
            service_status=status,
        )
        runtime_game_filter_mode = game_filter_state.effective_runtime_mode
        if not game_filter_state.enabled:
            clear_runtime_game_filter_override(self.cfg)

        external_present, external_hint = _detect_external_install(Path(self.cfg.zapret_dir), status.zapret_present)

        warnings: list[str] = []
        goodbye_dpi = service.goodbyedpi()
        if goodbye_dpi.found:
            warnings.append('Найден GoodbyeDPI — может конфликтовать с zapret.')

        needs_install = (
            (not status.zapret_present)
            or external_present
            or (status.service_state == 'NOT_INSTALLED')
        )

        return HomeState(
            zapret_present=status.zapret_present,
            service_state=status.service_state,
            capture_running=status.capture_running,
            enabled=enabled,
            current_strategy=current_strategy,
            selected_strategy=selected,
            strategies=strategies,
            external_present=external_present,
            external_hint=external_hint,
            show_install_zapret=needs_install,
            show_strategy_select=status.zapret_present and (not needs_install),
            show_apply_strategy=(
                (not needs_install)
                and bool(selected)
                and (normalize_strategy_key(selected) != normalize_strategy_key(current_strategy))
            ),
            show_remove_goodbyedpi=goodbye_dpi.found,
            warnings=warnings,
            runtime_game_filter_mode=runtime_game_filter_mode,
        )

    def install_zapret(self) -> tuple[bool, str]:
        state = self.build_state(self.cfg.last_strategy or '')
        service = self._service()

        if (not state.zapret_present) or state.external_present:
            result = service.install_or_update_zapret(version_tag=self.cfg.zapret_version or 'latest')
            return (result.ok, result.message)

        if state.service_state == 'NOT_INSTALLED':
            strategy = (state.selected_strategy or '').strip()
            if not strategy:
                strategies = service.strategies()
                strategy = strategies[0] if strategies else ''
            if not strategy:
                return (False, 'в папке zapret не найдено ни одной стратегии (*.bat)')
            result = service.install_service(strategy)
            return (result.ok, result.message or 'служба установлена')

        return (True, 'уже установлено')

    def toggle(self, on: bool, strategy: str) -> tuple[bool, str]:
        service = self._service()
        result = service.enable(on, strategy)
        if result.ok:
            if on:
                set_runtime_game_filter_override(self.cfg, self.cfg.game_filter_mode)
            else:
                clear_runtime_game_filter_override(self.cfg)
        return (result.ok, result.message)

    def install_service(self, strategy: str) -> tuple[bool, str]:
        result = self._service().install_service(strategy)
        return (result.ok, result.message)

    def apply_strategy(self, strategy: str) -> tuple[bool, str]:
        service = self._service()
        status_before = service.status()
        was_enabled = _status_is_enabled(status_before)

        result = service.apply_strategy(strategy)
        if not result.ok:
            return (False, result.message)

        if not was_enabled:
            disable_result = service.enable(False, '')
            if not disable_result.ok:
                return (False, _build_apply_strategy_error(result.message, disable_result.message))
            _wait_until_disabled(service)
            clear_runtime_game_filter_override(self.cfg)
            return (True, 'Стратегия применена. Zapret оставлен выключенным.')

        set_runtime_game_filter_override(self.cfg, self.cfg.game_filter_mode)
        return (True, result.message)

    def remove_services(self) -> tuple[bool, str]:
        result = self._service().remove_services()
        if result.ok:
            clear_runtime_game_filter_override(self.cfg)
        return (result.ok, result.message)

    def diagnostics_text(self) -> str:
        service = self._service()
        diagnostics = service.diagnostics()
        status = service.status()

        lines = [
            f'Service state: {diagnostics.service_state}',
            f'Capture running: {"YES" if diagnostics.capture_running else "NO"}',
            f'Current strategy: {status.current_strategy or "-"}',
            f'winws process: {diagnostics.winws_process_path or "-"}',
            f'our winws: {diagnostics.our_winws_path}',
        ]
        if diagnostics.winws_services:
            lines.append('WinWS services:')
            lines.extend(diagnostics.winws_services)
        return '\n'.join(lines)

    def remove_goodbyedpi(self) -> tuple[bool, str]:
        report = self._service().remove_goodbyedpi()
        parts: list[str] = []
        if report.removed_services:
            parts.append('Удалены службы: ' + ', '.join(report.removed_services))
        if report.killed_processes:
            parts.append('Завершены процессы: ' + ', '.join(report.killed_processes))
        return (True, '\n'.join(parts) if parts else 'Нечего удалять')

    def _resolve_selected_strategy(self, selected_strategy: str, current_strategy: str, strategies: list[str]) -> str:
        selected = (
            (selected_strategy or '').strip()
            or current_strategy
            or (self.cfg.last_strategy or '').strip()
        )
        if not strategies:
            return selected
        if not selected:
            return strategies[0]

        selected_key = normalize_strategy_key(selected)
        for strategy in strategies:
            if normalize_strategy_key(strategy) == selected_key:
                return strategy
        return strategies[0]

    def _service(self) -> ZapretService:
        return ZapretService(Path(self.cfg.zapret_dir), Path(self.cfg.data_dir))


def _status_is_enabled(status: object) -> bool:
    return (getattr(status, 'service_state', '') == 'RUNNING') or bool(getattr(status, 'capture_running', False))


def _build_apply_strategy_error(apply_message: str | None, disable_message: str | None) -> str:
    apply_tail = (apply_message or 'ok').strip()
    disable_tail = (disable_message or '').strip()
    return (
        apply_tail
        + '\n\nНе удалось выключить zapret после смены стратегии.\n'
        + disable_tail
    ).strip()


def _wait_until_disabled(service: ZapretService, timeout_s: float = 8.0) -> None:
    deadline = time.monotonic() + float(timeout_s)
    while time.monotonic() < deadline:
        if not _status_is_enabled(service.status()):
            return
        time.sleep(0.25)


def _detect_external_install(zapret_dir: Path, own_install_present: bool) -> tuple[bool, str]:
    own_winws_path = ''
    if own_install_present:
        own_winws_path = _normalize_path(str((zapret_dir / 'bin' / 'winws.exe').resolve()))

    running_path = _normalize_path((get_winws_process_path() or '').strip())
    service_path_pattern = re.compile(r'([A-Za-z]:\\[^"\']*?winws\.exe)', re.IGNORECASE)

    is_external = False
    hints: list[str] = []

    if running_path:
        if not own_install_present:
            is_external = True
            hints.append('Запущен winws.exe, но файлов zapret в папке приложения нет.')
        elif running_path != own_winws_path:
            is_external = True
            hints.append('Обнаружен winws.exe из другой папки.')

    for service_info in list_winws_services():
        service_name = (service_info.name or '').strip().casefold()
        if service_name != 'zapret':
            continue

        if not own_install_present:
            is_external = True
            hints.append('Служба zapret установлена, но файлов zapret в папке приложения нет.')
            break

        raw_path = (service_info.path or '').strip().replace('/', '\\')
        match = service_path_pattern.search(raw_path)
        if not match:
            continue

        service_winws_path = _normalize_path(match.group(1))
        if service_winws_path and service_winws_path != own_winws_path:
            is_external = True
            hints.append('Служба zapret использует winws.exe из другой папки (внешняя установка).')
            break

    return (is_external, ' '.join(hints).strip())


def _normalize_path(value: str) -> str:
    return (value or '').strip().strip('"').replace('/', '\\').casefold()
