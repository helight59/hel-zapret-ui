from __future__ import annotations

import json
import os
import re
from pathlib import Path

from src.cli.powershell import run_powershell
from src.cli.bat_cmdline import split_windows_cmdline

GAME_FILTER_DISABLED = 'disabled'
GAME_FILTER_ALL = 'all'
GAME_FILTER_TCP = 'tcp'
GAME_FILTER_UDP = 'udp'
GAME_FILTER_UNKNOWN = 'unknown'
_GAME_FILTER_RANGE = '1024-65535'
_GAME_FILTER_DISABLED_VALUE = '12'
_VALID_GAME_FILTER_MODES = {GAME_FILTER_DISABLED, GAME_FILTER_ALL, GAME_FILTER_TCP, GAME_FILTER_UDP}
_RUNTIME_OVERRIDE_ATTR = '_hel_runtime_game_filter_override_mode'




def is_known_game_filter_mode(value: str) -> bool:
    return (value or '').strip().lower() in _VALID_GAME_FILTER_MODES


def get_runtime_game_filter_override(cfg: object | None) -> str:
    if cfg is None:
        return ''
    value = normalize_game_filter_mode(str(getattr(cfg, _RUNTIME_OVERRIDE_ATTR, '') or ''))
    if value in _VALID_GAME_FILTER_MODES:
        return value
    return ''


def set_runtime_game_filter_override(cfg: object | None, mode: str) -> None:
    if cfg is None:
        return
    value = normalize_game_filter_mode(mode)
    if value not in _VALID_GAME_FILTER_MODES:
        value = ''
    setattr(cfg, _RUNTIME_OVERRIDE_ATTR, value)


def clear_runtime_game_filter_override(cfg: object | None) -> None:
    if cfg is None:
        return
    setattr(cfg, _RUNTIME_OVERRIDE_ATTR, '')


def resolve_runtime_game_filter_mode(raw_mode: str, enabled: bool, cfg: object | None = None) -> str:
    if not enabled:
        return GAME_FILTER_DISABLED
    override = get_runtime_game_filter_override(cfg)
    if override:
        return override
    mode = (raw_mode or '').strip().lower()
    if mode in _VALID_GAME_FILTER_MODES:
        return mode
    return GAME_FILTER_UNKNOWN

def normalize_game_filter_mode(value: str) -> str:
    mode = (value or '').strip().lower()
    if mode in ('', '0', 'off', 'false', 'disable', 'disabled', 'none'):
        return GAME_FILTER_DISABLED
    if mode in ('1', 'on', 'true', 'enable', 'enabled', 'all', 'tcp+udp', 'tcp and udp'):
        return GAME_FILTER_ALL
    if mode == GAME_FILTER_TCP:
        return GAME_FILTER_TCP
    if mode == GAME_FILTER_UDP:
        return GAME_FILTER_UDP
    return GAME_FILTER_DISABLED


def game_filter_flag_path(zapret_dir: Path) -> Path:
    return Path(zapret_dir) / 'utils' / 'game_filter.enabled'


def game_filter_available(zapret_dir: Path) -> bool:
    root = Path(zapret_dir)
    return (root / 'service.bat').exists() and (root / 'utils').exists()


def read_game_filter_mode(zapret_dir: Path) -> str:
    flag = game_filter_flag_path(zapret_dir)
    if not flag.exists() or (not flag.is_file()):
        return GAME_FILTER_DISABLED

    text = ''
    for enc in ('utf-8', 'cp1251', 'cp866'):
        try:
            text = flag.read_text(encoding=enc, errors='ignore')
            break
        except Exception:
            continue

    first_line = ''
    for line in (text or '').splitlines():
        first_line = (line or '').strip()
        if first_line:
            break

    return normalize_game_filter_mode(first_line)


def write_game_filter_mode(zapret_dir: Path, mode: str) -> bool:
    normalized = normalize_game_filter_mode(mode)
    flag = game_filter_flag_path(zapret_dir)
    if not flag.parent.exists():
        return False

    if normalized == GAME_FILTER_DISABLED:
        try:
            flag.unlink(missing_ok=True)
        except Exception:
            return False
        return True

    try:
        flag.write_text(normalized + '\n', encoding='utf-8')
    except Exception:
        return False
    return True


def read_runtime_game_filter_mode(zapret_dir: Path | str | None = None) -> str:
    root = Path(zapret_dir) if zapret_dir else None
    saw_any_cmdline = False
    for cmdline in _iter_runtime_cmdlines(root):
        saw_any_cmdline = True
        mode = _mode_from_cmdline(cmdline)
        if mode != GAME_FILTER_UNKNOWN:
            return mode
    return GAME_FILTER_UNKNOWN if saw_any_cmdline else GAME_FILTER_DISABLED


def _mode_from_cmdline(cmdline: str) -> str:
    argv = split_windows_cmdline((cmdline or '').strip())
    if not argv:
        return GAME_FILTER_UNKNOWN

    tcp_value = _extract_filter_value(argv, '--filter-tcp', '--wf-tcp')
    udp_value = _extract_filter_value(argv, '--filter-udp', '--wf-udp')
    if (not tcp_value) and (not udp_value):
        return GAME_FILTER_UNKNOWN

    tcp_game = _is_game_filter_value(tcp_value)
    udp_game = _is_game_filter_value(udp_value)
    tcp_disabled = _is_disabled_filter_value(tcp_value)
    udp_disabled = _is_disabled_filter_value(udp_value)

    if tcp_game and udp_game:
        return GAME_FILTER_ALL
    if tcp_game and (udp_disabled or (not udp_value) or (not udp_game)):
        return GAME_FILTER_TCP
    if udp_game and (tcp_disabled or (not tcp_value) or (not tcp_game)):
        return GAME_FILTER_UDP
    if tcp_disabled and udp_disabled:
        return GAME_FILTER_DISABLED
    if (not tcp_value) and udp_disabled:
        return GAME_FILTER_DISABLED
    if (not udp_value) and tcp_disabled:
        return GAME_FILTER_DISABLED
    return GAME_FILTER_UNKNOWN


def _iter_runtime_cmdlines(zapret_dir: Path | None) -> list[str]:
    cmdlines: list[str] = []

    preferred_processes = _get_preferred_winws_cmdlines(zapret_dir)
    for item in preferred_processes:
        if item and (item not in cmdlines):
            cmdlines.append(item)

    fallback = _get_any_winws_cmdline()
    if fallback and (fallback not in cmdlines):
        cmdlines.append(fallback)

    service_cmdline = _expand_service_runtime_cmdline('zapret')
    if service_cmdline and (service_cmdline not in cmdlines):
        cmdlines.append(service_cmdline)

    return cmdlines


def _get_preferred_winws_cmdlines(zapret_dir: Path | None) -> list[str]:
    rows = _list_winws_processes()
    if not rows:
        return []

    preferred_paths = _preferred_winws_paths(zapret_dir)
    if not preferred_paths:
        return []

    matched = [row.get('CommandLine', '') for row in rows if _norm_path(row.get('ExecutablePath', '')) in preferred_paths and row.get('CommandLine')]
    return matched


def _preferred_winws_paths(zapret_dir: Path | None) -> set[str]:
    out: set[str] = set()
    if zapret_dir:
        out.add(_norm_path(str(Path(zapret_dir) / 'bin' / 'winws.exe')))
    pd = os.environ.get('ProgramData') or r'C:\ProgramData'
    out.add(_norm_path(str(Path(pd) / 'hel-zapret' / 'zapret' / 'bin' / 'winws.exe')))
    return {x for x in out if x}


def _norm_path(value: str) -> str:
    p = (value or '').strip().strip('"').replace('/', '\\').lower()
    p = re.sub(r'\\+', r'\\', p)
    return p.rstrip('\\')


def _list_winws_processes() -> list[dict[str, str]]:
    cmd = (
        "Get-CimInstance Win32_Process -Filter \"Name='winws.exe'\" | "
        'Select-Object CommandLine,ExecutablePath | ConvertTo-Json -Compress'
    )
    txt = run_powershell(cmd)
    if not txt:
        return []
    try:
        data = json.loads(txt)
    except Exception:
        return []

    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        return []

    out: list[dict[str, str]] = []
    for row in data:
        if not isinstance(row, dict):
            continue
        out.append({
            'CommandLine': str(row.get('CommandLine') or '').strip(),
            'ExecutablePath': str(row.get('ExecutablePath') or '').strip(),
        })
    return out


def _expand_service_runtime_cmdline(name: str) -> str:
    service_path = _get_service_pathname(name)
    if not service_path:
        return ''

    wrapper_cmdline = _read_wrapper_target(service_path)
    if wrapper_cmdline:
        return wrapper_cmdline
    return service_path


def _read_wrapper_target(service_path: str) -> str:
    wrapper_path = _extract_wrapper_cmd_path(service_path)
    if not wrapper_path:
        return ''

    p = Path(wrapper_path)
    if not p.exists() or (not p.is_file()):
        return ''

    text = ''
    for enc in ('utf-8', 'cp1251', 'cp866'):
        try:
            text = p.read_text(encoding=enc, errors='ignore')
            break
        except Exception:
            continue

    first_fallback = ''
    for line in (text or '').replace('\r', '\n').split('\n'):
        candidate = (line or '').strip()
        low = candidate.lower()
        if not candidate:
            continue
        if low in ('@echo off', 'setlocal'):
            continue
        if low.startswith('exit /b'):
            continue
        if ('winws.exe' in low) or ('--filter-tcp' in low) or ('--filter-udp' in low):
            return candidate
        if not first_fallback:
            first_fallback = candidate
    return first_fallback


def _extract_wrapper_cmd_path(service_path: str) -> str:
    m = re.search(r'([A-Za-z]:\\[^"\r\n]+?\.(?:cmd|bat))', service_path or '', flags=re.IGNORECASE)
    if m:
        return m.group(1)

    for arg in split_windows_cmdline(service_path or ''):
        low = arg.lower()
        if low.endswith('.cmd') or low.endswith('.bat'):
            return arg
    return ''


def _extract_filter_value(argv: list[str], *options: str) -> str:
    keys = [(option or '').strip().lower() for option in options if (option or '').strip()]
    if not keys:
        return ''

    for i, arg in enumerate(argv):
        low = (arg or '').strip().lower()
        for key in keys:
            if low.startswith(key + '='):
                return _normalize_filter_value(low.split('=', 1)[1])
            if low == key:
                nxt = argv[i + 1] if (i + 1) < len(argv) else ''
                return _normalize_filter_value(nxt)
    return ''


def _normalize_filter_value(value: str) -> str:
    return str(value or '').strip().strip('"').strip("'").lower()


def _split_filter_tokens(value: str) -> list[str]:
    normalized = _normalize_filter_value(value)
    if not normalized:
        return []
    parts = re.split(r'[;,\s]+', normalized)
    return [part for part in parts if part]


def _is_game_filter_value(value: str) -> bool:
    tokens = _split_filter_tokens(value)
    if not tokens:
        return False
    return _GAME_FILTER_RANGE in tokens


def _is_disabled_filter_value(value: str) -> bool:
    tokens = _split_filter_tokens(value)
    if not tokens:
        return False
    return tokens == [_GAME_FILTER_DISABLED_VALUE] or ((len(tokens) == 1) and (tokens[0] == _GAME_FILTER_DISABLED_VALUE))


def _get_any_winws_cmdline() -> str:
    cmd = "(Get-CimInstance Win32_Process -Filter \"Name='winws.exe'\" | Select-Object -First 1 -ExpandProperty CommandLine)"
    return run_powershell(cmd)


def _get_service_pathname(name: str) -> str:
    cmd = f"(Get-CimInstance Win32_Service -Filter \"Name='{name}'\" | Select-Object -First 1 -ExpandProperty PathName)"
    return run_powershell(cmd)
