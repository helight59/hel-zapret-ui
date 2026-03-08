from __future__ import annotations

from pathlib import Path


USER_LIST_FIELD_TO_FILE = {
    'custom_forward_domains': 'list-general-user.txt',
    'custom_blocked_domains': 'list-exclude-user.txt',
    'custom_excluded_ips': 'ipset-exclude-user.txt',
}

_USER_LIST_PLACEHOLDERS = {
    'domain.example.abc',
    '203.0.113.113/32',
}

_USER_LIST_ENCODINGS = ('utf-8', 'utf-8-sig', 'cp1251', 'cp866')


def normalize_user_list(value: object) -> list[str]:
    if isinstance(value, str):
        raw_values = value.splitlines()
    elif isinstance(value, (list, tuple)):
        raw_values = list(value)
    else:
        return []

    result: list[str] = []
    seen: set[str] = set()
    for raw in raw_values:
        text = str(raw or '').strip()
        if not text or text in _USER_LIST_PLACEHOLDERS:
            continue
        key = text.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def read_user_list_file(path: Path) -> list[str]:
    if not path.exists():
        return []

    text = _read_text_with_fallback(path)
    return normalize_user_list(text)


def read_user_lists_dir(path: Path) -> dict[str, list[str]]:
    return {
        field_name: read_user_list_file(path / file_name)
        for field_name, file_name in USER_LIST_FIELD_TO_FILE.items()
    }


def _read_text_with_fallback(path: Path) -> str:
    for encoding in _USER_LIST_ENCODINGS:
        try:
            return path.read_text(encoding=encoding)
        except Exception:
            continue

    try:
        return path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return ''
