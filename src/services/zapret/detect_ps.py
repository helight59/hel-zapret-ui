import re
from dataclasses import dataclass
from src.cli.powershell import run_powershell
from src.services.windows.tasks import get_process_path

@dataclass
class WinwsService:
    name: str
    state: str
    path: str

def get_winws_process_path() -> str:
    return get_process_path('winws')

def list_winws_services() -> list[WinwsService]:
    cmd = (
        "Get-CimInstance Win32_Service | "
        "Where-Object { $_.PathName -match 'winws\\.exe|_hel_zapret_run\\.cmd' } | "
        "Select-Object Name,State,PathName | Format-List"
    )
    txt = run_powershell(cmd)
    if not txt:
        return []
    blocks = re.split(r"\n\s*\n", txt.replace("\r", ""))
    out: list[WinwsService] = []
    for b in blocks:
        name = _pick(b, "Name")
        state = _pick(b, "State")
        path = _pick(b, "PathName")
        if name or path:
            out.append(WinwsService(name=name, state=state, path=path))
    return out

def _pick(block: str, key: str) -> str:
    for line in block.split("\n"):
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        if k.strip().lower() == key.lower():
            return v.strip()
    return ""