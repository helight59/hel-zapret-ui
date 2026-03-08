from dataclasses import dataclass
from typing import Iterable
from src.cli.process import run
from src.services.zapret.detect import detect_winws_services, detect_goodbyedpi_services, is_process_running

@dataclass
class CleanupReport:
    removed_services: list[str]
    stopped_services: list[str]
    killed_processes: list[str]


@dataclass
class GoodbyeDpiDetection:
    found: bool
    services: list
    process_running: bool

def _stop_service(name: str) -> bool:
    r = run(['sc', 'stop', name])
    return r.code == 0

def _delete_service(name: str) -> bool:
    r = run(['sc', 'delete', name])
    return r.code == 0

def _kill_process(image: str) -> bool:
    if not is_process_running(image):
        return False
    r = run(['taskkill', '/IM', image, '/F'])
    return r.code == 0

def remove_winws_services(exclude: set[str] | None = None) -> CleanupReport:
    exclude = exclude or set()
    removed: list[str] = []
    stopped: list[str] = []
    killed: list[str] = []
    for s in detect_winws_services():
        if s.name in exclude:
            continue
        _stop_service(s.name)
        stopped.append(s.name)
        if _delete_service(s.name):
            removed.append(s.name)
    if _kill_process('winws.exe'):
        killed.append('winws.exe')
    return CleanupReport(removed_services=removed, stopped_services=stopped, killed_processes=killed)

def detect_goodbyedpi():
    services = detect_goodbyedpi_services()
    proc = is_process_running('goodbyedpi.exe')
    found = bool(services) or proc
    return GoodbyeDpiDetection(found=found, services=services, process_running=proc)

def remove_goodbyedpi() -> CleanupReport:
    removed: list[str] = []
    stopped: list[str] = []
    killed: list[str] = []
    for s in detect_goodbyedpi_services():
        _stop_service(s.name)
        stopped.append(s.name)
        if _delete_service(s.name):
            removed.append(s.name)
    if _kill_process('goodbyedpi.exe'):
        killed.append('goodbyedpi.exe')
    return CleanupReport(removed_services=removed, stopped_services=stopped, killed_processes=killed)

def kill_processes(images: Iterable[str]) -> list[str]:
    killed = []
    for img in images:
        if _kill_process(img):
            killed.append(img)
    return killed