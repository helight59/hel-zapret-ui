from src.cli.bat_cmdline import (
    expand_bat_vars,
    extract_winws_args_from_bat_text,
    split_windows_cmdline,
)
from src.cli.launcher import LaunchResult, start_winws_from_bat
from src.cli.powershell import run_powershell
from src.cli.process import CmdResult, popen_capture, run
from src.cli.service_bat import (
    RunResult,
    clean_via_menu,
    install_service,
    remove_services,
    run_tests_via_cli,
    run_tests_via_menu,
)
from src.cli.tests_patch import ensure_tests_cli_support

__all__ = [
    'CmdResult',
    'LaunchResult',
    'RunResult',
    'clean_via_menu',
    'ensure_tests_cli_support',
    'expand_bat_vars',
    'extract_winws_args_from_bat_text',
    'install_service',
    'popen_capture',
    'remove_services',
    'run',
    'run_powershell',
    'run_tests_via_cli',
    'run_tests_via_menu',
    'split_windows_cmdline',
    'start_winws_from_bat',
]
