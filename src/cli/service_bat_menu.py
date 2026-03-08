import re
from typing import Iterable


PROMPT_MAIN_RE = re.compile(r'(?is)select option\s*\(\s*\d+\s*-\s*\d+\s*\)\s*:\s*$')
PROMPT_SELECT_RE = re.compile(r'(?is)select\s+.+?\(\s*\d+\s*-\s*\d+\s*\)\s*:\s*$')
PROMPT_FILE_INDEX_RE = re.compile(r'(?is)(input|enter)\s+file\s+index.*?:\s*$|file\s+index\s*\(.+?\)\s*:\s*$')
PRESS_ANY_KEY_RE = re.compile(r'(?is)press any key to continue')
DELETE_OK_RE = re.compile(r'(?is)\[sc\]\s+deleteservice\s+success')
INSTALL_OK_RE = re.compile(r'(?is)\[sc\].*create(service)?\s+success|service\s+installed|install\s+success')
ERROR_RE = re.compile(r'(?is)\b(failed|error)\b|\[sc\]\s+.*\s+failed')
SERVICE_MISSING_RE = re.compile(r'(?is)(does\s+not\s+exist\s+as\s+an\s+installed\s+service|not\s+installed|не\s+существует\s+как\s+служб|служб\w*\s+не\s+существует)')
BAT_LINE_RE = re.compile(r'(?im)^\s*\d{1,3}\s*[).:\-]\s*.*?\.bat\b')
TEST_TYPE_PROMPT_RE = re.compile(r'(?is)select\s+test\s+type.*?enter\s+1\s+or\s+2\s*:\s*$')
TEST_MODE_PROMPT_RE = re.compile(r'(?is)select\s+test\s+run\s+mode.*?enter\s+1\s+or\s+2\s*:\s*$')


def looks_like_main_menu(text: str) -> bool:
    if not text:
        return False
    plain = text.replace('\r', '')
    low = plain.lower()
    if 'zapret service manager' in low and PROMPT_MAIN_RE.search(plain):
        return True
    if PROMPT_MAIN_RE.search(plain) and ('install service' in low or 'remove services' in low or 'check status' in low):
        return True
    return False


def looks_like_strategy_menu(text: str) -> bool:
    if not text:
        return False
    plain = text.replace('\r', '')
    if not BAT_LINE_RE.search(plain):
        return False
    return bool(PROMPT_SELECT_RE.search(plain) or PROMPT_FILE_INDEX_RE.search(plain))


def strip_press_any_key(text: str) -> str:
    return re.sub(r'(?is)press any key to continue\s*\.\s*\.\s*\.\s*', '', text)


def find_menu_number(text: str, needles: Iterable[str]) -> str:
    lines = (text or '').replace('\r', '').split('\n')
    lowered = [needle.lower() for needle in needles]
    for line in lines[-8000:]:
        low = line.lower()
        if any(needle in low for needle in lowered):
            match = re.match(r'^\s*(\d{1,3})\s*[).:\-]\s*', line)
            if match:
                return match.group(1)
    for line in lines[-8000:]:
        low = line.lower()
        if any(needle in low for needle in lowered):
            match = re.search(r'\b(\d{1,3})\b', line)
            if match:
                return match.group(1)
    return ''


def find_strategy_number(text: str, strategy_name: str) -> str:
    target = (strategy_name or '').lower()
    if not target:
        return ''
    lines = (text or '').replace('\r', '').split('\n')
    for line in lines[-12000:]:
        low = line.lower()
        if '.bat' in low and target in low:
            match = re.match(r'^\s*(\d{1,3})\s*[).:\-]\s*', line)
            if match:
                return match.group(1)
    for line in lines[-12000:]:
        low = line.lower()
        if target in low:
            match = re.match(r'^\s*(\d{1,3})\s*[).:\-]\s*', line)
            if match:
                return match.group(1)
    for line in lines[-12000:]:
        if target in line.lower():
            match = re.search(r'\b(\d{1,3})\b', line)
            if match:
                return match.group(1)
    return ''


def parse_available_configs(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (text or '').replace('\r', '').split('\n')[-20000:]:
        if '.bat' not in line.lower():
            continue
        match = re.match(r'^\s*(\d{1,3})\s*[).:\-]\s*(.+?\.bat)\b', line, flags=re.IGNORECASE)
        if not match:
            continue
        idx = match.group(1)
        name = match.group(2).strip()
        out[name.lower()] = idx
        if name.lower().endswith('.bat'):
            out[name[:-4].lower()] = idx
    return out


def normalize_strategy_name(strategy_bat: str) -> str:
    value = (strategy_bat or '').strip()
    if value.lower().endswith('.bat'):
        value = value[:-4]
    return re.sub(r'\s+', ' ', value).strip()
