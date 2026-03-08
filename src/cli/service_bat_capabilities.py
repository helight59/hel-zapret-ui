import re
from pathlib import Path


def read_service_bat_text(zapret_root: Path) -> str:
    path = zapret_root / 'service.bat'
    if not path.exists():
        return ''
    for encoding in ('cp866', 'utf-8'):
        try:
            return path.read_text(encoding=encoding, errors='ignore')
        except Exception:
            continue
    try:
        return path.read_text(errors='ignore')
    except Exception:
        return ''


def service_bat_supports_label(zapret_root: Path, label: str) -> bool:
    if not label:
        return False
    text = read_service_bat_text(zapret_root)
    if not text:
        return False
    return bool(re.search(rf'(?im)^\s*:{re.escape(label)}\b', text))


def service_bat_supports_tests_cli(zapret_root: Path) -> bool:
    return service_bat_supports_label(zapret_root, 'run_tests_cli')
