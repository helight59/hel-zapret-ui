import sys
from src.services.security.elevation import ensure_elevated
from src.app.app import run_app

def main() -> int:
    ensure_elevated()
    return run_app()

if __name__ == '__main__':
    raise SystemExit(main())