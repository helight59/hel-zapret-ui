from pathlib import Path
import re


class ZapretLayout:
    def __init__(self, root: Path):
        self.root = root

    def ok(self) -> bool:
        return (
            (self.root / 'bin' / 'winws.exe').exists()
            and (self.root / 'lists').exists()
            and (self.root / 'utils').exists()
        )

    def list_strategies(self) -> list[str]:
        if not self.root.exists():
            return []

        strategies: list[str] = []
        for batch_file in self.root.glob('*.bat'):
            name = batch_file.name
            lowered_name = name.casefold()
            if lowered_name == 'service.bat' or 'service' in lowered_name:
                continue
            strategies.append(name)

        strategies.sort(key=_natural_key)
        return strategies

    def local_version(self) -> str:
        if not self.root.exists():
            return ''

        version = _read_version_marker(self.root)
        if version:
            return version

        return _read_version_from_service_bat(self.root / 'service.bat')


def _read_version_marker(root: Path) -> str:
    for path in (
        root / '.service' / 'version.txt',
        root / 'version.txt',
        root / 'VERSION',
        root / 'version',
    ):
        try:
            if not path.is_file():
                continue
            version = path.read_text(encoding='utf-8', errors='ignore').strip()
            if version:
                return version
        except Exception:
            continue
    return ''


def _read_version_from_service_bat(path: Path) -> str:
    try:
        if not path.is_file():
            return ''
        text = path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return ''

    for pattern in (
        r'(?im)^\s*set\s+"LOCAL_VERSION=([^\"]+)"\s*$',
        r'(?im)^\s*set\s+LOCAL_VERSION\s*=\s*([^\s&]+)\s*$',
    ):
        match = re.search(pattern, text)
        if not match:
            continue
        version = (match.group(1) or '').strip()
        if version.casefold().startswith('v'):
            version = version[1:]
        if version:
            return version

    match = re.search(r'\bv\s*(\d+(?:\.\d+)+)\b', text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return ''


def _natural_key(value: str) -> list[int | str]:
    parts = re.split(r'(\d+)', value)
    key: list[int | str] = []
    for part in parts:
        if part.isdigit():
            key.append(int(part))
        else:
            key.append(part.casefold())
    return key
