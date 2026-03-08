import re
from dataclasses import dataclass
from src.services.windows.tasks import is_process_running
from src.cli.process import run

@dataclass
class CandidateService:
    name: str
    image_path: str

def _parse_services_imagepath() -> list[CandidateService]:
    r = run(['reg', 'query', r'HKLM\SYSTEM\CurrentControlSet\Services', '/s', '/v', 'ImagePath'])
    txt = r.out
    out: list[CandidateService] = []
    cur = ''
    for line in txt.splitlines():
        if line.startswith('HKEY_LOCAL_MACHINE\\SYSTEM\\CurrentControlSet\\Services\\'):
            cur = line.strip()
            continue
        if 'ImagePath' in line:
            parts = re.split(r'\s{2,}', line.strip())
            if len(parts) >= 3:
                img = parts[2]
                name = cur.split('\\')[-1] if cur else 'unknown'
                out.append(CandidateService(name=name, image_path=img))
    return out

def detect_winws_services() -> list[CandidateService]:
    out = []
    for s in _parse_services_imagepath():
        if 'winws.exe' in s.image_path.lower():
            out.append(s)
    return out

def detect_goodbyedpi_services() -> list[CandidateService]:
    out = []
    for s in _parse_services_imagepath():
        if 'goodbyedpi' in s.image_path.lower():
            out.append(s)
    return out