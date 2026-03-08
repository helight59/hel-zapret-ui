from __future__ import annotations
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from src.cli.powershell import run_powershell
from src.cli.bat_cmdline import extract_winws_args_from_bat_text, expand_bat_vars, split_windows_cmdline

@dataclass
class StrategyDetection:
    strategy: str
    source: str
    cmdline: str

def detect_current_strategy(zapret_root: Path) -> StrategyDetection:
    reg = _get_service_strategy_from_registry()
    if reg:
        return StrategyDetection(strategy=reg, source='REGISTRY', cmdline='')

    cmdline = _get_winws_cmdline() or _get_service_pathname('zapret') or ''
    cmdline = cmdline.strip()
    if not cmdline:
        return StrategyDetection(strategy='', source='NONE', cmdline='')

    strat = _extract_bat_from_cmdline(cmdline)
    if strat:
        return StrategyDetection(strategy=strat, source='CMDLINE_BAT', cmdline=cmdline)

    args = _extract_winws_args_from_cmdline(cmdline)
    if not args:
        return StrategyDetection(strategy='', source='NO_ARGS', cmdline=cmdline)

    best = _match_strategy_by_args(zapret_root, args)
    if best:
        return StrategyDetection(strategy=best, source='ARGS_MATCH', cmdline=cmdline)

    return StrategyDetection(strategy='', source='UNKNOWN', cmdline=cmdline)


def _get_service_strategy_from_registry() -> str:
    if not sys.platform.startswith('win'):
        return ''
    try:
        import winreg
    except Exception:
        return ''

    key_path = r'SYSTEM\\CurrentControlSet\\Services\\zapret'
    try:
        k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
    except Exception:
        return ''

    try:
        i = 0
        while True:
            try:
                name, val, typ = winreg.EnumValue(k, i)
            except OSError:
                break
            i += 1
            if typ != getattr(winreg, 'REG_SZ', 1):
                continue
            n = (name or '').strip().lower()
            if 'zapret' not in n:
                continue
            v = (val or '').strip().strip('"')
            if not v:
                continue
            if (':' in v) or ('\\' in v) or ('/' in v):
                continue
            if len(v) > 96:
                continue
            return v
    finally:
        try:
            winreg.CloseKey(k)
        except Exception:
            pass

    return ''

def _get_winws_cmdline() -> str:
    cmd = "(Get-CimInstance Win32_Process -Filter \"Name='winws.exe'\" | Select-Object -First 1 -ExpandProperty CommandLine)"
    return run_powershell(cmd)

def _get_service_pathname(name: str) -> str:
    cmd = f"(Get-CimInstance Win32_Service -Filter \"Name='{name}'\" | Select-Object -First 1 -ExpandProperty PathName)"
    return run_powershell(cmd)

def _extract_bat_from_cmdline(cmdline: str) -> str:
    low = cmdline.lower()
    m = re.search(r'([a-z0-9_\-\.]+\.bat)\b', low)
    if not m:
        return ''
    return Path(m.group(1)).name

def _extract_winws_args_from_cmdline(cmdline: str) -> list[str]:
    argv = split_windows_cmdline(cmdline)
    if not argv:
        return []
    exe_i = -1
    for i, a in enumerate(argv):
        if a.lower().endswith('winws.exe'):
            exe_i = i
            break
    if exe_i >= 0:
        return argv[exe_i + 1:]
    return argv[1:] if len(argv) > 1 else []

def _match_strategy_by_args(zapret_root: Path, args: list[str]) -> str:
    bats = _list_strategies(zapret_root)
    if not bats:
        return ''
    target = _parse_args_profile(_cleanup_args(args), zapret_root)
    if target.is_empty():
        return ''

    best_name = ''
    best_score = -1
    best_detail = None

    for bat in bats:
        bat_args = _extract_strategy_args(zapret_root, bat)
        if not bat_args:
            continue
        cand = _parse_args_profile(_cleanup_args(bat_args), zapret_root)
        if cand.is_empty():
            continue
        score, detail = _score_profiles(target, cand)
        if score > best_score:
            best_score = score
            best_name = bat
            best_detail = detail

    if not best_name:
        return ''

    if best_score < 12:
        return ''

    if best_detail:
        if best_detail.get('pair_hits', 0) >= 2:
            return best_name
        if best_detail.get('key_hits', 0) >= 5:
            return best_name

    return ''

def _list_strategies(root: Path) -> list[str]:
    if not root.exists():
        return []
    out: list[str] = []
    for p in root.glob('*.bat'):
        n = p.name
        low = n.lower()
        if low == 'service.bat':
            continue
        if 'service' in low:
            continue
        out.append(n)
    out.sort()
    return out

def _extract_strategy_args(zapret_root: Path, bat_name: str) -> list[str]:
    bat_path = zapret_root / bat_name
    if not bat_path.exists():
        return []
    text = bat_path.read_text(encoding='utf-8', errors='ignore')
    args_s = extract_winws_args_from_bat_text(text)
    if not args_s:
        return []
    args_s = expand_bat_vars(args_s, zapret_root)
    return split_windows_cmdline(args_s)

def _cleanup_args(args: list[str]) -> list[str]:
    out: list[str] = []
    skip_next = False
    noise = {'cmd.exe', 'cmd', '/c', 'start', 'call'}
    redirects = {'>', '1>', '2>', '>>', '1>>', '2>>', '<', '2>&1', '1>&2'}
    for a in args:
        if skip_next:
            skip_next = False
            continue
        x = a.strip()
        if not x:
            continue
        low = x.lower()
        if low in noise:
            continue
        if low in redirects:
            continue
        if low in {'&', '&&', '|', '||'}:
            continue
        if low in {'/min', '/b'}:
            continue
        if low.startswith('>') or low.startswith('1>') or low.startswith('2>'):
            continue
        if low.endswith('.log') and (len(out) > 0 and out[-1] in {'>', '>>', '1>', '1>>', '2>', '2>>'}):
            continue
        if low == 'nul':
            continue
        if low in {'-windowstyle', '-noprofile', '-executionpolicy', 'bypass', '-command'}:
            continue
        out.append(x)
    return out

class _ArgsProfile:
    def __init__(self, keys: set[str], pairs: dict[str, set[str]], positional: set[str]):
        self.keys = keys
        self.pairs = pairs
        self.positional = positional

    def is_empty(self) -> bool:
        return (not self.keys) and (not self.pairs) and (not self.positional)

def _parse_args_profile(args: list[str], root: Path) -> _ArgsProfile:
    keys: set[str] = set()
    pairs: dict[str, set[str]] = {}
    positional: set[str] = set()

    i = 0
    while i < len(args):
        raw = args[i]
        tok = _norm_token(raw, root)
        if not tok:
            i += 1
            continue

        k, v = _split_kv(tok)
        if _is_key(k):
            keys.add(k)
            if v is not None:
                pairs.setdefault(k, set()).add(_norm_value(v, root))
                i += 1
                continue

            if i + 1 < len(args):
                nxt_raw = args[i + 1]
                nxt = _norm_token(nxt_raw, root)
                if nxt and (not _looks_like_key(nxt_raw)):
                    pairs.setdefault(k, set()).add(_norm_value(nxt, root))
                    i += 2
                    continue

            i += 1
            continue

        positional.add(tok)
        i += 1

    return _ArgsProfile(keys=keys, pairs=pairs, positional=positional)

def _looks_like_key(raw: str) -> bool:
    s = raw.strip()
    return s.startswith('--') or s.startswith('-') or s.startswith('/')

def _is_key(k: str) -> bool:
    return bool(k) and (k.startswith('--') or k.startswith('-') or k.startswith('/'))

def _split_kv(tok: str) -> tuple[str, str | None]:
    if '=' in tok:
        a, b = tok.split('=', 1)
        a = a.strip()
        b = b.strip()
        if _is_key(a) and b != '':
            return a, b
    return tok, None

def _norm_token(t: str, root: Path) -> str:
    x = t.strip().strip('"').strip("'")
    x = x.replace('/', '\\')
    x = re.sub(r'\\+', r'\\', x)
    x = x.strip()
    if not x:
        return ''
    return x.lower()

def _norm_value(v: str, root: Path) -> str:
    x = v.strip().strip('"').strip("'")
    x = x.replace('/', '\\')
    x = re.sub(r'\\+', r'\\', x)
    x = x.lower()
    if _looks_like_path(x):
        x = _normalize_path_value(x, root)
    return x

def _looks_like_path(x: str) -> bool:
    if '\\' in x or '/' in x:
        return True
    if x.endswith('.txt') or x.endswith('.bin') or x.endswith('.dat') or x.endswith('.json') or x.endswith('.ini'):
        return True
    if x.endswith('.exe') or x.endswith('.dll'):
        return True
    return False

def _normalize_path_value(x: str, root: Path) -> str:
    s = x.strip().strip('"')
    s = s.replace('/', '\\')
    s = re.sub(r'\\+', r'\\', s)
    if s.startswith('.\\'):
        s = str((root / s[2:]).resolve())
    return s.lower()

def _score_profiles(a: _ArgsProfile, b: _ArgsProfile) -> tuple[int, dict[str, int]]:
    score = 0
    detail: dict[str, int] = {'key_hits': 0, 'pair_hits': 0, 'pos_hits': 0, 'path_pair_hits': 0}

    key_common = a.keys & b.keys
    detail['key_hits'] = len(key_common)
    score += len(key_common) * 2

    pair_hits = 0
    path_pair_hits = 0
    keys_union = set(a.pairs.keys()) | set(b.pairs.keys())
    for k in keys_union:
        av = a.pairs.get(k) or set()
        bv = b.pairs.get(k) or set()
        if (not av) or (not bv):
            continue

        for va in av:
            for vb in bv:
                if va == vb:
                    pair_hits += 1
                    if _looks_like_path(va) or _looks_like_path(vb):
                        path_pair_hits += 1
                    continue
                if _maybe_path_equivalent(va, vb):
                    pair_hits += 1
                    path_pair_hits += 1

    detail['pair_hits'] = pair_hits
    detail['path_pair_hits'] = path_pair_hits
    score += pair_hits * 6
    score += path_pair_hits * 4

    pos_common = a.positional & b.positional
    detail['pos_hits'] = len(pos_common)
    score += len(pos_common) * 1

    if (a.keys == b.keys) and (len(a.keys) >= 4):
        score += 6

    return score, detail

def _maybe_path_equivalent(a: str, b: str) -> bool:
    if not (_looks_like_path(a) or _looks_like_path(b)):
        return False
    pa = a.replace('/', '\\')
    pb = b.replace('/', '\\')
    if pa == pb:
        return True
    na = Path(pa).name
    nb = Path(pb).name
    if na and nb and na == nb:
        return True
    return False