from __future__ import annotations

from dataclasses import dataclass

from src.services.zapret.game_filter import GAME_FILTER_DISABLED, is_known_game_filter_mode, normalize_game_filter_mode
from src.services.zapret.game_filter_state import GameFilterState

_DIRTY_FLAG_ATTR = '_hel_game_filter_editor_dirty'
_DIRTY_MODE_ATTR = '_hel_game_filter_editor_dirty_mode'


@dataclass(frozen=True)
class GameFilterEditorState:
    dirty: bool
    service_mode: str
    service_enabled: bool
    desired_mode: str
    base_mode: str
    ui_mode: str
    ui_enabled: bool


def get_game_filter_service_mode(state: GameFilterState) -> str:
    if not bool(getattr(state, 'enabled', False)):
        return GAME_FILTER_DISABLED
    mode = normalize_game_filter_mode(str(getattr(state, 'effective_runtime_mode', '') or ''))
    if is_known_game_filter_mode(mode):
        return mode
    return GAME_FILTER_DISABLED


def is_game_filter_editor_dirty(cfg: object | None) -> bool:
    return bool(getattr(cfg, _DIRTY_FLAG_ATTR, False)) if cfg is not None else False


def get_game_filter_editor_dirty_mode(cfg: object | None) -> str:
    if cfg is None:
        return GAME_FILTER_DISABLED
    mode = normalize_game_filter_mode(str(getattr(cfg, _DIRTY_MODE_ATTR, '') or ''))
    if is_known_game_filter_mode(mode):
        return mode
    return GAME_FILTER_DISABLED


def set_game_filter_editor_dirty_mode(cfg: object | None, mode: str) -> None:
    if cfg is None:
        return
    normalized = normalize_game_filter_mode(mode)
    if not is_known_game_filter_mode(normalized):
        normalized = GAME_FILTER_DISABLED
    setattr(cfg, _DIRTY_FLAG_ATTR, True)
    setattr(cfg, _DIRTY_MODE_ATTR, normalized)


def clear_game_filter_editor_dirty(cfg: object | None) -> None:
    if cfg is None:
        return
    setattr(cfg, _DIRTY_FLAG_ATTR, False)
    setattr(cfg, _DIRTY_MODE_ATTR, '')


def sync_game_filter_editor_dirty(cfg: object | None, state: GameFilterState) -> bool:
    if not is_game_filter_editor_dirty(cfg):
        return False
    if get_game_filter_service_mode(state) != get_game_filter_editor_dirty_mode(cfg):
        return False
    clear_game_filter_editor_dirty(cfg)
    return True


def make_game_filter_editor_state(state: GameFilterState, cfg: object | None = None) -> GameFilterEditorState:
    service_mode = get_game_filter_service_mode(state)
    desired_mode = normalize_game_filter_mode(str(getattr(state, 'desired_mode', '') or ''))
    if not is_known_game_filter_mode(desired_mode):
        desired_mode = GAME_FILTER_DISABLED
    dirty = is_game_filter_editor_dirty(cfg)
    base_mode = service_mode if bool(getattr(state, 'enabled', False)) else desired_mode
    ui_mode = get_game_filter_editor_dirty_mode(cfg) if dirty else base_mode
    if not is_known_game_filter_mode(ui_mode):
        ui_mode = GAME_FILTER_DISABLED
    return GameFilterEditorState(
        dirty=dirty,
        service_mode=service_mode,
        service_enabled=(service_mode != GAME_FILTER_DISABLED),
        desired_mode=desired_mode,
        base_mode=base_mode,
        ui_mode=ui_mode,
        ui_enabled=(ui_mode != GAME_FILTER_DISABLED),
    )
