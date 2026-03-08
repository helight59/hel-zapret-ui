from src.cli.process import run


def run_powershell(command: str) -> str:
    r = run(['powershell.exe', '-NoProfile', '-Command', command])
    return (r.out or '').strip()
