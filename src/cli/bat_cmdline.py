import re
from pathlib import Path


def extract_winws_args_from_bat_text(text: str) -> str:
    t = text.replace('\r', '\n')
    lines = [x.strip() for x in t.split('\n') if x.strip()]
    for ln in lines:
        low = ln.lower()
        if 'winws.exe' not in low:
            continue
        idx = low.find('winws.exe')
        after = ln[idx + len('winws.exe'):]
        after = after.lstrip(' "\'')
        after = after.replace('^', ' ')
        after = re.sub(r'\s+', ' ', after).strip()
        return after
    return ''


def expand_bat_vars(args: str, root: Path) -> str:
    a = args
    a = a.replace('%~dp0', str(root) + '\\')
    a = a.replace('%~dp0bin\\', str(root / 'bin') + '\\')
    a = a.replace('%~dp0lists\\', str(root / 'lists') + '\\')
    a = a.replace('%~dp0utils\\', str(root / 'utils') + '\\')
    return a


def split_windows_cmdline(s: str) -> list[str]:
    out: list[str] = []
    cur = ''
    q = False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == '"':
            q = not q
            i += 1
            continue
        if (not q) and ch.isspace():
            if cur:
                out.append(cur)
                cur = ''
            i += 1
            while i < len(s) and s[i].isspace():
                i += 1
            continue
        cur += ch
        i += 1
    if cur:
        out.append(cur)
    return out
