from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.services.zapret.game_filter import (
    GAME_FILTER_ALL,
    GAME_FILTER_DISABLED,
    GAME_FILTER_TCP,
    GAME_FILTER_UDP,
    GAME_FILTER_UNKNOWN,
    game_filter_available,
    is_known_game_filter_mode,
    normalize_game_filter_mode,
    read_game_filter_mode,
    read_runtime_game_filter_mode,
    resolve_runtime_game_filter_mode,
)
from src.services.zapret.service import ZapretService


@dataclass(frozen=True)
class GameFilterState:
    available: bool
    enabled: bool
    desired_mode: str
    runtime_mode: str
    effective_runtime_mode: str
    runtime_mode_known: bool
    restart_required: bool


_STATUS_LABELS = {
    GAME_FILTER_ALL: 'TCP + UDP',
    GAME_FILTER_UDP: 'Только UDP',
    GAME_FILTER_TCP: 'Только TCP',
    GAME_FILTER_DISABLED: 'Выключен',
}


def format_game_filter_status(enabled: bool, mode: str) -> str:
    if not enabled:
        return 'Выключен'
    normalized_mode = (mode or '').strip().lower()
    return _STATUS_LABELS.get(normalized_mode, 'Не определён')


def format_runtime_game_filter_state(state: GameFilterState) -> str:
    return format_game_filter_status(state.enabled, state.effective_runtime_mode)


def make_game_filter_state(
    desired_mode: str,
    enabled: bool,
    runtime_mode: str,
    *,
    available: bool,
    cfg: object | None = None,
) -> GameFilterState:
    desired = _normalize_known_mode(desired_mode, fallback=GAME_FILTER_DISABLED)
    runtime = _normalize_runtime_mode(runtime_mode, enabled)
    effective_runtime = resolve_runtime_game_filter_mode(runtime, enabled, cfg)
    runtime_known = is_known_game_filter_mode(runtime)

    return GameFilterState(
        available=bool(available),
        enabled=bool(enabled),
        desired_mode=desired,
        runtime_mode=runtime,
        effective_runtime_mode=effective_runtime,
        runtime_mode_known=runtime_known,
        restart_required=bool(enabled and available and (desired != effective_runtime)),
    )


def sync_desired_game_filter_mode(zapret_dir: Path | str, cfg: object | None = None) -> str:
    root = Path(zapret_dir)
    desired_mode = _read_desired_mode(root, cfg)
    if cfg is None:
        return desired_mode

    current_mode = _normalize_known_mode(
        str(getattr(cfg, 'game_filter_mode', '') or ''),
        fallback=GAME_FILTER_DISABLED,
    )
    if desired_mode != current_mode:
        setattr(cfg, 'game_filter_mode', desired_mode)
        save = getattr(cfg, 'save', None)
        if callable(save):
            save()
    return desired_mode


def read_game_filter_state(
    zapret_dir: Path | str,
    data_dir: Path | str,
    cfg: object | None = None,
    *,
    service_status: object | None = None,
) -> GameFilterState:
    root = Path(zapret_dir)
    available = game_filter_available(root)
    desired_mode = sync_desired_game_filter_mode(root, cfg)

    enabled = False
    runtime_mode = GAME_FILTER_DISABLED
    try:
        status = service_status
        if status is None:
            status = ZapretService(root, Path(data_dir)).status()
        enabled = _service_status_is_enabled(status)
        if enabled:
            runtime_mode = read_runtime_game_filter_mode(root)
    except Exception:
        enabled = False
        runtime_mode = GAME_FILTER_UNKNOWN

    return make_game_filter_state(
        desired_mode,
        enabled,
        runtime_mode,
        available=available,
        cfg=cfg,
    )


def _read_desired_mode(zapret_dir: Path, cfg: object | None = None) -> str:
    if game_filter_available(zapret_dir):
        return _normalize_known_mode(read_game_filter_mode(zapret_dir), fallback=GAME_FILTER_DISABLED)
    if cfg is None:
        return GAME_FILTER_DISABLED
    return _normalize_known_mode(
        str(getattr(cfg, 'game_filter_mode', '') or ''),
        fallback=GAME_FILTER_DISABLED,
    )


def _normalize_runtime_mode(mode: str, enabled: bool) -> str:
    if not enabled:
        return GAME_FILTER_DISABLED
    normalized_mode = (mode or '').strip().lower()
    if normalized_mode == GAME_FILTER_UNKNOWN:
        return GAME_FILTER_UNKNOWN
    return _normalize_known_mode(normalized_mode, fallback=GAME_FILTER_UNKNOWN)


def _normalize_known_mode(mode: str, *, fallback: str) -> str:
    normalized_mode = normalize_game_filter_mode(mode)
    if is_known_game_filter_mode(normalized_mode):
        return normalized_mode
    return fallback


def _service_status_is_enabled(status: object) -> bool:
    return (
        str(getattr(status, 'service_state', '') or '').strip().upper() == 'RUNNING'
    ) or bool(getattr(status, 'capture_running', False))
