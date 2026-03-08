from __future__ import annotations

import json
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path


GITHUB_REPO = 'Flowseal/zapret-discord-youtube'
GITHUB_API = f'https://api.github.com/repos/{GITHUB_REPO}'
_REQUEST_HEADERS = {'User-Agent': 'hel-zapret-ui'}


@dataclass
class ZapretRelease:
    tag: str
    version: str
    published_at: str
    zip_url: str


def list_releases(data_dir: Path, min_version: str = '1.9.4', cache_ttl_s: int = 6 * 60 * 60) -> list[ZapretRelease]:
    cache_path = Path(data_dir) / 'releases_cache.json'
    cached_payload = _read_cache(cache_path)
    now = int(time.time())

    if _cache_is_fresh(cached_payload, now, cache_ttl_s):
        cached_releases = _parse_releases(cached_payload.get('items', []), min_version)
        if cached_releases:
            return cached_releases

    live_payload = _load_json_url(f'{GITHUB_API}/releases?per_page=100')
    if isinstance(live_payload, list):
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps({'ts': now, 'items': live_payload}, ensure_ascii=False),
            encoding='utf-8',
        )
        live_releases = _parse_releases(live_payload, min_version)
        if live_releases:
            return live_releases

    if cached_payload:
        return _parse_releases(cached_payload.get('items', []), min_version)
    return []


def resolve_zip_asset(tag: str) -> str:
    clean_tag = (tag or '').strip()
    if not clean_tag:
        return ''

    if clean_tag.casefold() == 'latest':
        url = f'{GITHUB_API}/releases/latest'
    else:
        url = f'{GITHUB_API}/releases/tags/{clean_tag}'

    payload = _load_json_url(url)
    if not isinstance(payload, dict):
        return ''

    return _pick_release_asset_url(payload)


def _read_cache(path: Path) -> dict:
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding='utf-8'))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _cache_is_fresh(payload: dict, now: int, ttl_s: int) -> bool:
    ts = payload.get('ts', 0)
    return bool(payload) and isinstance(ts, int) and (now - ts < ttl_s)


def _load_json_url(url: str) -> object:
    try:
        request = urllib.request.Request(url, headers=_REQUEST_HEADERS)
        with urllib.request.urlopen(request, timeout=12) as response:
            raw = response.read().decode('utf-8', errors='ignore')
        return json.loads(raw)
    except Exception:
        return None


def _parse_releases(items: list, min_version: str) -> list[ZapretRelease]:
    min_version_tuple = _parse_ver(min_version)
    if min_version_tuple is None:
        return []

    releases: list[ZapretRelease] = []
    for item in items:
        release = _parse_release_item(item, min_version_tuple)
        if release is not None:
            releases.append(release)

    releases.sort(key=lambda release: _parse_ver(release.version) or (0, 0, 0), reverse=True)
    return releases


def _parse_release_item(item: object, min_version: tuple[int, int, int]) -> ZapretRelease | None:
    if not isinstance(item, dict):
        return None

    tag = str(item.get('tag_name', '') or '').strip()
    if not tag:
        return None

    version = _clean_tag(tag)
    version_tuple = _parse_ver(version)
    if version_tuple is None or version_tuple < min_version:
        return None

    return ZapretRelease(
        tag=tag,
        version=version,
        published_at=str(item.get('published_at', '') or ''),
        zip_url=_pick_release_asset_url(item),
    )


def _pick_release_asset_url(payload: dict) -> str:
    assets = payload.get('assets', []) or []
    fallback_url = ''
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        download_url = str(asset.get('browser_download_url', '') or '')
        if not download_url:
            continue
        if not fallback_url:
            fallback_url = download_url
        asset_name = str(asset.get('name', '') or '').casefold()
        if asset_name.endswith('.zip'):
            return download_url
    return fallback_url


def _clean_tag(tag: str) -> str:
    clean_tag = (tag or '').strip()
    if clean_tag.casefold().startswith('v'):
        return clean_tag[1:]
    return clean_tag


def _parse_ver(version: str) -> tuple[int, int, int] | None:
    parts = (version or '').strip().split('.')
    if len(parts) < 2:
        return None

    try:
        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2]) if len(parts) > 2 else 0
    except Exception:
        return None

    return (major, minor, patch)
