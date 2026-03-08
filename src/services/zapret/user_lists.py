from __future__ import annotations

from pathlib import Path

from src.app.config import AppConfig
from src.app.user_lists import USER_LIST_FIELD_TO_FILE, normalize_user_list, read_user_list_file

LIST_GENERAL_USER = USER_LIST_FIELD_TO_FILE['custom_forward_domains']
LIST_EXCLUDE_USER = USER_LIST_FIELD_TO_FILE['custom_blocked_domains']
IPSET_EXCLUDE_USER = USER_LIST_FIELD_TO_FILE['custom_excluded_ips']

def normalize_entries(values: list[str] | tuple[str, ...] | None) -> list[str]:
    return normalize_user_list(list(values or []))


def write_user_list_file(path: Path, values: list[str] | tuple[str, ...] | None) -> None:
    lines = normalize_user_list(list(values or []))
    path.parent.mkdir(parents=True, exist_ok=True)
    text = '\n'.join(lines)
    if text:
        text += '\n'
    path.write_text(text, encoding='utf-8', newline='')


def read_existing_user_lists(zapret_dir: Path) -> dict[str, list[str]]:
    lists_dir = Path(zapret_dir) / 'lists'
    out: dict[str, list[str]] = {}
    for field_name, file_name in USER_LIST_FIELD_TO_FILE.items():
        out[field_name] = read_user_list_file(lists_dir / file_name)
    return out


def sync_saved_user_lists(zapret_dir: Path, data_dir: Path) -> bool:
    root = Path(zapret_dir)
    if not root.exists():
        return False

    lists_dir = root / 'lists'
    lists_dir.mkdir(parents=True, exist_ok=True)

    cfg = AppConfig.load(data_dir)
    values_map = {
        'custom_forward_domains': cfg.custom_forward_domains,
        'custom_blocked_domains': cfg.custom_blocked_domains,
        'custom_excluded_ips': cfg.custom_excluded_ips,
    }

    ok = True
    for field_name, file_name in USER_LIST_FIELD_TO_FILE.items():
        try:
            write_user_list_file(lists_dir / file_name, values_map.get(field_name) or [])
        except Exception:
            ok = False
    return ok
