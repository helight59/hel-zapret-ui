from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.services.zapret.game_filter import GAME_FILTER_ALL, GAME_FILTER_DISABLED, GAME_FILTER_TCP, GAME_FILTER_UDP
from src.services.zapret.game_filter_state import GameFilterState
from src.services.zapret.game_filter_ui_state import clear_game_filter_editor_dirty, is_game_filter_editor_dirty, make_game_filter_editor_state, set_game_filter_editor_dirty_mode, sync_game_filter_editor_dirty


class GameFilterUiStateTests(unittest.TestCase):
    def _state(self, *, enabled: bool, desired: str, runtime: str) -> GameFilterState:
        return GameFilterState(
            available=True,
            enabled=enabled,
            desired_mode=desired,
            runtime_mode=runtime,
            effective_runtime_mode=runtime if enabled else GAME_FILTER_DISABLED,
            runtime_mode_known=True,
            restart_required=(desired != (runtime if enabled else GAME_FILTER_DISABLED)),
        )

    def test_without_dirty_editor_follows_saved_mode_when_service_stopped(self) -> None:
        cfg = SimpleNamespace()
        state = self._state(enabled=False, desired=GAME_FILTER_ALL, runtime=GAME_FILTER_DISABLED)

        ui = make_game_filter_editor_state(state, cfg)

        self.assertFalse(ui.dirty)
        self.assertTrue(ui.ui_enabled)
        self.assertEqual(ui.base_mode, GAME_FILTER_ALL)
        self.assertEqual(ui.ui_mode, GAME_FILTER_ALL)
        self.assertEqual(ui.desired_mode, GAME_FILTER_ALL)

    def test_without_dirty_editor_follows_service_when_running(self) -> None:
        cfg = SimpleNamespace()
        state = self._state(enabled=True, desired=GAME_FILTER_UDP, runtime=GAME_FILTER_TCP)

        ui = make_game_filter_editor_state(state, cfg)

        self.assertFalse(ui.dirty)
        self.assertTrue(ui.ui_enabled)
        self.assertEqual(ui.base_mode, GAME_FILTER_TCP)
        self.assertEqual(ui.ui_mode, GAME_FILTER_TCP)
        self.assertEqual(ui.desired_mode, GAME_FILTER_UDP)

    def test_dirty_editor_keeps_user_choice_before_apply(self) -> None:
        cfg = SimpleNamespace()
        set_game_filter_editor_dirty_mode(cfg, GAME_FILTER_UDP)
        state = self._state(enabled=False, desired=GAME_FILTER_ALL, runtime=GAME_FILTER_DISABLED)

        ui = make_game_filter_editor_state(state, cfg)

        self.assertTrue(ui.dirty)
        self.assertTrue(ui.ui_enabled)
        self.assertEqual(ui.ui_mode, GAME_FILTER_UDP)

    def test_dirty_clears_when_service_matches_choice(self) -> None:
        cfg = SimpleNamespace()
        set_game_filter_editor_dirty_mode(cfg, GAME_FILTER_TCP)
        state = self._state(enabled=True, desired=GAME_FILTER_TCP, runtime=GAME_FILTER_TCP)

        changed = sync_game_filter_editor_dirty(cfg, state)
        ui = make_game_filter_editor_state(state, cfg)

        self.assertTrue(changed)
        self.assertFalse(is_game_filter_editor_dirty(cfg))
        self.assertFalse(ui.dirty)
        self.assertTrue(ui.ui_enabled)
        self.assertEqual(ui.ui_mode, GAME_FILTER_TCP)

    def test_dirty_not_cleared_while_service_differs(self) -> None:
        cfg = SimpleNamespace()
        set_game_filter_editor_dirty_mode(cfg, GAME_FILTER_TCP)
        state = self._state(enabled=True, desired=GAME_FILTER_TCP, runtime=GAME_FILTER_ALL)

        changed = sync_game_filter_editor_dirty(cfg, state)
        ui = make_game_filter_editor_state(state, cfg)

        self.assertFalse(changed)
        self.assertTrue(ui.dirty)
        self.assertEqual(ui.ui_mode, GAME_FILTER_TCP)

    def test_clear_dirty_resets_to_saved_mode_when_service_stopped(self) -> None:
        cfg = SimpleNamespace()
        set_game_filter_editor_dirty_mode(cfg, GAME_FILTER_UDP)
        clear_game_filter_editor_dirty(cfg)
        state = self._state(enabled=False, desired=GAME_FILTER_TCP, runtime=GAME_FILTER_DISABLED)

        ui = make_game_filter_editor_state(state, cfg)

        self.assertFalse(ui.dirty)
        self.assertEqual(ui.ui_mode, GAME_FILTER_TCP)


if __name__ == '__main__':
    unittest.main()
