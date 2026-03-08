from __future__ import annotations

import logging
import shutil
from pathlib import Path

from src.utils.paths import bundle_dir


def ensure_zapret_seed(zapret_dir: Path) -> None:
    target = Path(zapret_dir)
    if (target / 'bin' / 'winws.exe').exists():
        return

    seed = bundle_dir() / 'zapret'
    if not (seed / 'bin' / 'winws.exe').exists():
        return

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(seed, target, dirs_exist_ok=True)
        logging.info('bootstrap: copied zapret from %s to %s', seed, target)
    except Exception as exc:
        logging.warning('bootstrap: failed to seed zapret: %s', exc)
