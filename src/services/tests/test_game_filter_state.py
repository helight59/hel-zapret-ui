from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src.services.zapret.game_filter import GAME_FILTER_ALL, GAME_FILTER_DISABLED, GAME_FILTER_TCP, GAME_FILTER_UDP, GAME_FILTER_UNKNOWN, set_runtime_game_filter_override
from src.services.zapret.game_filter_state import make_game_filter_state, sync_desired_game_filter_mode


class _Cfg:
    def __init__(self, mode: str = GAME_FILTER_DISABLED):
        self.game_filter_mode = mode
        self.saved = 0

    def save(self) -> None:
        self.saved += 1


class GameFilterStateTests(unittest.TestCase):
    def test_make_state_for_running_all_mode(self) -> None:
        state = make_game_filter_state(GAME_FILTER_ALL, True, GAME_FILTER_ALL, available=True)
        self.assertTrue(state.enabled)
        self.assertEqual(state.runtime_mode, GAME_FILTER_ALL)
        self.assertEqual(state.effective_runtime_mode, GAME_FILTER_ALL)
        self.assertFalse(state.restart_required)

    def test_make_state_detects_restart_requirement(self) -> None:
        state = make_game_filter_state(GAME_FILTER_TCP, True, GAME_FILTER_UDP, available=True)
        self.assertEqual(state.desired_mode, GAME_FILTER_TCP)
        self.assertEqual(state.runtime_mode, GAME_FILTER_UDP)
        self.assertTrue(state.restart_required)

    def test_make_state_uses_runtime_override_consistently(self) -> None:
        cfg = _Cfg(GAME_FILTER_TCP)
        set_runtime_game_filter_override(cfg, GAME_FILTER_TCP)
        state = make_game_filter_state(GAME_FILTER_TCP, True, GAME_FILTER_UNKNOWN, available=True, cfg=cfg)
        self.assertEqual(state.runtime_mode, GAME_FILTER_UNKNOWN)
        self.assertEqual(state.effective_runtime_mode, GAME_FILTER_TCP)
        self.assertFalse(state.restart_required)

    def test_make_state_for_disabled_service(self) -> None:
        state = make_game_filter_state(GAME_FILTER_ALL, False, GAME_FILTER_UNKNOWN, available=True)
        self.assertFalse(state.enabled)
        self.assertEqual(state.runtime_mode, GAME_FILTER_DISABLED)
        self.assertEqual(state.effective_runtime_mode, GAME_FILTER_DISABLED)
        self.assertFalse(state.restart_required)

    def test_sync_desired_mode_reads_flag_and_updates_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'utils').mkdir(parents=True)
            (root / 'service.bat').write_text('echo ok\n', encoding='utf-8')
            (root / 'utils' / 'game_filter.enabled').write_text('udp\n', encoding='utf-8')
            cfg = _Cfg(GAME_FILTER_DISABLED)
            mode = sync_desired_game_filter_mode(root, cfg)
            self.assertEqual(mode, GAME_FILTER_UDP)
            self.assertEqual(cfg.game_filter_mode, GAME_FILTER_UDP)
            self.assertEqual(cfg.saved, 1)


if __name__ == '__main__':
    unittest.main()
