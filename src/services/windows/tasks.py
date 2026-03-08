from __future__ import annotations

from src.cli.powershell import run_powershell
from src.cli.process import run


def is_process_running(image_name: str) -> bool:
    r = run(['tasklist', '/FI', f'IMAGENAME eq {image_name}'])
    txt = (r.out + r.err).lower()
    return image_name.lower() in txt and 'no tasks are running' not in txt and 'не запущено' not in txt


def kill_process(image_name: str) -> bool:
    r = run(['taskkill', '/IM', image_name, '/F'])
    return r.code == 0


def get_process_path(process_name: str) -> str:
    name = process_name
    if name.lower().endswith('.exe'):
        name = name[:-4]
    cmd = f"(Get-Process {name} -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Path)"
    return run_powershell(cmd)
