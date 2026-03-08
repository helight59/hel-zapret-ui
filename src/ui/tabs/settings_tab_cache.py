from __future__ import annotations

import logging
import shutil
from pathlib import Path


cache_log = logging.getLogger('cache')


def cache_targets(data_dir: Path) -> list[Path]:
    return [data_dir / 'releases_cache.json', data_dir / 'history', data_dir / 'backup']


def cache_size_bytes(data_dir: Path) -> int:
    total = 0
    targets = list(cache_targets(data_dir))
    try:
        targets.extend(sorted(data_dir.glob('app.log*')))
    except Exception:
        pass
    for path in targets:
        if not path.exists():
            continue
        if path.is_file():
            try:
                total += int(path.stat().st_size)
            except Exception:
                pass
            continue
        for file in path.rglob('*'):
            try:
                if file.is_file():
                    total += int(file.stat().st_size)
            except Exception:
                pass
    return total


def detach_app_log(log_path: Path) -> None:
    try:
        root = logging.getLogger()
        try:
            want = log_path.resolve()
        except Exception:
            want = None
        for handler in list(root.handlers):
            if not isinstance(handler, logging.FileHandler):
                continue
            base = getattr(handler, 'baseFilename', '')
            if not base:
                continue
            try:
                got = Path(base).resolve()
            except Exception:
                got = None
            if want is not None and got is not None:
                if got != want:
                    continue
            elif str(base).lower() != str(log_path).lower():
                continue
            try:
                root.removeHandler(handler)
            except Exception:
                pass
            try:
                handler.flush()
            except Exception:
                pass
            try:
                handler.close()
            except Exception:
                pass
    except Exception:
        return


def attach_app_log(log_path: Path) -> None:
    try:
        from src.utils.logging_setup import create_file_handler
        root = logging.getLogger()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        root.addHandler(create_file_handler(log_path))
    except Exception:
        return


def clear_cache(data_dir: Path) -> bool:
    cache_log.info('clear cache start dir=%s', str(data_dir))
    log_path = data_dir / 'app.log'
    detach_app_log(log_path)
    try:
        for file in sorted(data_dir.glob('app.log*')):
            try:
                if file.is_file():
                    file.unlink(missing_ok=True)
            except Exception:
                pass
    except Exception:
        pass

    for target in cache_targets(data_dir):
        if not target.exists():
            continue
        try:
            if target.is_dir():
                shutil.rmtree(target, ignore_errors=True)
            else:
                target.unlink(missing_ok=True)
        except Exception:
            pass

    attach_app_log(log_path)
    cache_log.info('clear cache done')
    return True


def fmt_bytes(size: int) -> str:
    value = float(max(int(size), 0))
    units = ['Б', 'КБ', 'МБ', 'ГБ']
    unit = 0
    while value >= 1024.0 and unit < len(units) - 1:
        value /= 1024.0
        unit += 1
    if unit == 0:
        return f'{int(value)} {units[unit]}'
    return f'{value:.1f} {units[unit]}'
