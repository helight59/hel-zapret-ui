import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path

from src.app.user_lists import USER_LIST_FIELD_TO_FILE, normalize_user_list, read_user_lists_dir


def _default_data_dir() -> Path:
    base = os.environ.get('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
    return Path(base) / 'hel_zapret_ui'


def _data_dir_for(data_dir: str | Path | None) -> str:
    if data_dir is None:
        return str(_default_data_dir())
    return str(Path(data_dir))


def _zapret_dir_for(data_dir: str | Path) -> str:
    return str(Path(data_dir) / 'zapret')


def _read_legacy_user_lists(zapret_dir: str | Path) -> dict[str, list[str]]:
    return read_user_lists_dir(Path(zapret_dir) / 'lists')


@dataclass
class AppConfig:
    zapret_dir: str
    data_dir: str
    remove_windivert_on_remove: bool
    autostart_enabled: bool
    zapret_version: str
    last_strategy: str
    game_filter_mode: str
    window_width: int
    window_height: int
    custom_forward_domains: list[str]
    custom_blocked_domains: list[str]
    custom_excluded_ips: list[str]

    @staticmethod
    def default(data_dir: str | Path | None = None) -> 'AppConfig':
        resolved_data_dir = _data_dir_for(data_dir)
        return AppConfig(
            zapret_dir=_zapret_dir_for(resolved_data_dir),
            data_dir=resolved_data_dir,
            remove_windivert_on_remove=False,
            autostart_enabled=True,
            zapret_version='latest',
            last_strategy='',
            game_filter_mode='disabled',
            window_width=1080,
            window_height=560,
            custom_forward_domains=[],
            custom_blocked_domains=[],
            custom_excluded_ips=[],
        )

    @staticmethod
    def load(data_dir: str | Path | None = None) -> 'AppConfig':
        cfg = AppConfig.default(data_dir)
        p = Path(cfg.data_dir) / 'config.json'
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            if p.exists():
                raw_obj = json.loads(p.read_text(encoding='utf-8'))
                raw = raw_obj if isinstance(raw_obj, dict) else {}
                merged = {**asdict(cfg), **raw}
                merged['zapret_dir'] = _zapret_dir_for(str(merged.get('data_dir') or cfg.data_dir))

                legacy_lists = _read_legacy_user_lists(merged['zapret_dir'])
                for field_name in USER_LIST_FIELD_TO_FILE:
                    value = merged.get(field_name)
                    normalized = normalize_user_list(value)
                    if (field_name not in raw) and legacy_lists.get(field_name):
                        normalized = legacy_lists[field_name]
                    merged[field_name] = normalized

                keys = set(asdict(cfg).keys())
                cfg2 = AppConfig(**{k: merged[k] for k in keys})

                if isinstance(raw_obj, dict):
                    updated = dict(raw_obj)
                    missing = False
                    for k, v in asdict(cfg2).items():
                        if k not in updated:
                            updated[k] = v
                            missing = True
                    updated['zapret_dir'] = cfg2.zapret_dir
                    if missing:
                        p.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding='utf-8')

                return cfg2

            legacy_lists = _read_legacy_user_lists(cfg.zapret_dir)
            for field_name in USER_LIST_FIELD_TO_FILE:
                setattr(cfg, field_name, legacy_lists.get(field_name) or [])
            cfg.save()
        except Exception:
            return cfg
        return cfg

    def save(self) -> None:
        self.zapret_dir = _zapret_dir_for(self.data_dir)
        self.custom_forward_domains = normalize_user_list(self.custom_forward_domains)
        self.custom_blocked_domains = normalize_user_list(self.custom_blocked_domains)
        self.custom_excluded_ips = normalize_user_list(self.custom_excluded_ips)
        p = Path(self.data_dir) / 'config.json'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding='utf-8')
