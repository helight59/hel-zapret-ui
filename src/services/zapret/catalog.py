from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.services.updater.release_catalog import ZapretRelease, list_releases


@dataclass
class ZapretVersionItem:
    tag: str
    label: str
    published_at: str


def available_versions(data_dir: Path, min_version: str = '1.9.4') -> list[ZapretVersionItem]:
    rel = list_releases(data_dir=data_dir, min_version=min_version)
    out: list[ZapretVersionItem] = [ZapretVersionItem(tag='latest', label='latest', published_at='')]
    for r in rel:
        out.append(ZapretVersionItem(tag=r.tag, label=r.version, published_at=r.published_at))
    return out
