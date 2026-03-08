import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from src.cli.service_bat_capabilities import service_bat_supports_label, service_bat_supports_tests_cli
from src.cli.service_bat_io import CREATE_NO_WINDOW, LineEmitter, PipeCollector, kill_process, wait_exit_or_timeout, write_stdin
from src.cli.service_bat_menu import (
    DELETE_OK_RE,
    ERROR_RE,
    INSTALL_OK_RE,
    PRESS_ANY_KEY_RE,
    PROMPT_FILE_INDEX_RE,
    PROMPT_SELECT_RE,
    SERVICE_MISSING_RE,
    TEST_MODE_PROMPT_RE,
    TEST_TYPE_PROMPT_RE,
    find_menu_number,
    find_strategy_number,
    looks_like_main_menu,
    looks_like_strategy_menu,
    normalize_strategy_name,
    parse_available_configs,
    strip_press_any_key,
)


log = logging.getLogger('service_menu')


@dataclass
class RunResult:
    ok: bool
    message: str
    output: str


def remove_services(zapret_root: Path, parse_wait_s: float = 0.0, menu_wait_s: float = 25.0, total_timeout_s: float = 120.0) -> RunResult:
    if service_bat_supports_label(zapret_root, 'remove_cli'):
        return _run_cli_action(zapret_root, 'remove_cli', [], total_timeout_s=total_timeout_s)
    return _run_flow(zapret_root, 'remove', '', parse_wait_s, menu_wait_s, total_timeout_s)


def install_service(zapret_root: Path, strategy_bat: str, parse_wait_s: float = 0.0, menu_wait_s: float = 25.0, total_timeout_s: float = 180.0) -> RunResult:
    strategy = (strategy_bat or '').strip()
    if strategy and service_bat_supports_label(zapret_root, 'install_cli'):
        return _run_cli_action(zapret_root, 'install_cli', [strategy], total_timeout_s=total_timeout_s)
    return _run_flow(zapret_root, 'install', normalize_strategy_name(strategy_bat), parse_wait_s, menu_wait_s, total_timeout_s)


def clean_via_menu(zapret_root: Path, parse_wait_s: float = 0.0, menu_wait_s: float = 25.0, total_timeout_s: float = 180.0) -> RunResult:
    return _run_flow(zapret_root, 'clean', '', parse_wait_s, menu_wait_s, total_timeout_s)


def run_tests_via_menu(
    zapret_root: Path,
    test_type: str,
    configs: list[str] | None = None,
    parse_wait_s: float = 0.0,
    menu_wait_s: float = 25.0,
    total_timeout_s: float = 1800.0,
    is_cancelled=None,
    on_output_line=None,
) -> RunResult:
    kind = (test_type or '').strip().lower()
    if kind not in ('standard', 'dpi'):
        return RunResult(False, 'unknown test type', '')
    cfgs = configs or []
    if service_bat_supports_tests_cli(zapret_root):
        return run_tests_via_cli(
            zapret_root,
            test_type=kind,
            configs=cfgs,
            total_timeout_s=total_timeout_s,
            is_cancelled=is_cancelled,
            on_output_line=on_output_line,
        )
    return _run_flow(zapret_root, 'tests', kind, parse_wait_s, menu_wait_s, total_timeout_s, cfgs=cfgs, is_cancelled=is_cancelled)


def run_tests_via_cli(
    zapret_root: Path,
    test_type: str,
    configs: list[str] | None = None,
    total_timeout_s: float = 1800.0,
    is_cancelled=None,
    on_output_line=None,
) -> RunResult:
    kind = (test_type or '').strip().lower()
    if kind not in ('standard', 'dpi'):
        return RunResult(False, 'unknown test type', '')

    cfgs = configs or []
    mode = 'select' if cfgs else 'all'
    cfg_csv = ';'.join(cfgs)
    service_bat = zapret_root / 'service.bat'
    if not service_bat.exists():
        log.error('service.bat not found: %s', str(service_bat))
        return RunResult(False, 'service.bat not found', '')
    if not service_bat_supports_tests_cli(zapret_root):
        return RunResult(False, 'run_tests_cli not supported by service.bat', '')

    argv = [
        'cmd.exe', '/d', '/q', '/c', 'call', str(service_bat),
        'admin', 'run_tests_cli', kind, mode, cfg_csv,
    ]
    return _run_cli_subprocess(
        zapret_root,
        argv,
        f'tests_cli kind={kind} mode={mode}',
        total_timeout_s,
        is_cancelled=is_cancelled,
        on_output_line=on_output_line,
    )


def _run_cli_action(
    zapret_root: Path,
    action: str,
    args: list[str] | None = None,
    total_timeout_s: float = 120.0,
    is_cancelled=None,
    on_output_line=None,
) -> RunResult:
    action_name = (action or '').strip()
    if not action_name:
        return RunResult(False, 'action is empty', '')

    service_bat = zapret_root / 'service.bat'
    if not service_bat.exists():
        log.error('service.bat not found: %s', str(service_bat))
        return RunResult(False, 'service.bat not found', '')
    if not service_bat_supports_label(zapret_root, action_name):
        return RunResult(False, f'{action_name} not supported by service.bat', '')

    argv = ['cmd.exe', '/d', '/q', '/c', 'call', str(service_bat), 'admin', action_name] + (args or [])
    return _run_cli_subprocess(
        zapret_root,
        argv,
        action_name,
        total_timeout_s,
        is_cancelled=is_cancelled,
        on_output_line=on_output_line,
    )


def _run_cli_subprocess(
    zapret_root: Path,
    argv: list[str],
    label: str,
    total_timeout_s: float,
    is_cancelled=None,
    on_output_line=None,
) -> RunResult:
    env = dict(os.environ)
    env['NO_UPDATE_CHECK'] = '1'
    env['HEL_ZAPRET_UI_TESTS'] = '1'

    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0

    try:
        process = subprocess.Popen(
            argv,
            cwd=str(zapret_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='cp866',
            errors='replace',
            env=env,
            startupinfo=startup,
            creationflags=CREATE_NO_WINDOW,
            bufsize=0,
        )
    except Exception as exc:
        log.exception('spawn %s failed', label)
        return RunResult(False, str(exc), '')

    collector = PipeCollector(process)
    collector.start()
    emitter = LineEmitter(on_output_line)
    output = ''
    started = time.monotonic()

    try:
        while True:
            if is_cancelled and is_cancelled():
                output = _drain_output(collector, emitter, output)
                kill_process(process)
                output = _drain_output(collector, emitter, output)
                emitter.flush()
                return RunResult(False, 'cancelled', output or '')

            output = _drain_output(collector, emitter, output)

            if process.poll() is not None:
                output = _drain_output(collector, emitter, output)
                emitter.flush()
                ok = (process.returncode == 0) and (not ERROR_RE.search(output))
                return RunResult(ok, f'exit code {process.returncode}', output or '')

            if time.monotonic() - started > total_timeout_s:
                log.error('%s timeout %.2fs. output\n%s', label, total_timeout_s, output if output else '<empty>')
                kill_process(process)
                output = _drain_output(collector, emitter, output)
                emitter.flush()
                return RunResult(False, 'timeout', output or '')

            time.sleep(0.05)
    finally:
        try:
            if process.stdout:
                process.stdout.close()
        except Exception:
            pass


def _run_flow(
    zapret_root: Path,
    mode: str,
    strategy_name: str,
    parse_wait_s: float,
    menu_wait_s: float,
    total_timeout_s: float,
    cfgs: list[str] | None = None,
    is_cancelled=None,
) -> RunResult:
    service_bat = zapret_root / 'service.bat'
    if not service_bat.exists():
        log.error('service.bat not found: %s', str(service_bat))
        return RunResult(False, 'service.bat not found', '')

    env = dict(os.environ)
    env['NO_UPDATE_CHECK'] = '1'
    env['HEL_ZAPRET_UI_TESTS'] = '1'

    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0

    try:
        process = subprocess.Popen(
            ['cmd.exe', '/d', '/q', '/c', 'call', str(service_bat), 'admin'],
            cwd=str(zapret_root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='cp866',
            errors='replace',
            env=env,
            startupinfo=startup,
            creationflags=CREATE_NO_WINDOW,
            bufsize=0,
        )
    except Exception as exc:
        log.exception('spawn failed')
        return RunResult(False, str(exc), '')

    collector = PipeCollector(process)
    collector.start()
    output = collector.drain()
    log.debug('snapshot (no fixed sleep; parse_wait_s=%.2fs):\n%s', parse_wait_s, output if output else '<empty>')

    try:
        menu_ready, output = _wait_main_menu(process, collector, output, menu_wait_s)
        if not menu_ready:
            output += collector.drain()
            log.error('menu not detected within %.2fs. output:\n%s', menu_wait_s, output if output else '<empty>')
            kill_process(process)
            output += collector.drain()
            return RunResult(False, 'menu not detected', output or '')

        if mode == 'remove':
            remove_num = find_menu_number(output, ['Remove Services', 'Удалить службы', 'Remove service', 'Удаление служб'])
            exit_num = find_menu_number(output, ['Exit', 'Выход', 'Quit', 'Close'])
            if not remove_num:
                kill_process(process)
                return RunResult(False, 'cannot parse Remove Services', output or '')
            ok, msg, output = _run_remove_flow(process, collector, output, remove_num, exit_num, total_timeout_s)
            return RunResult(ok, msg, output or '')

        if mode == 'install':
            install_num = find_menu_number(output, ['Install Service', 'Установить службу', 'Install service', 'Установка службы'])
            exit_num = find_menu_number(output, ['Exit', 'Выход', 'Quit', 'Close'])
            if not install_num:
                kill_process(process)
                return RunResult(False, 'cannot parse Install Service', output or '')
            ok, msg, output = _run_install_flow(process, collector, output, install_num, exit_num, strategy_name, total_timeout_s)
            return RunResult(ok, msg, output or '')

        if mode == 'clean':
            clean_num = find_menu_number(output, ['Clean', 'Cleanup', 'Clear', 'Очист', 'Чист', 'Сброс'])
            exit_num = find_menu_number(output, ['Exit', 'Выход', 'Quit', 'Close'])
            if not clean_num:
                kill_process(process)
                return RunResult(False, 'cannot parse Clean option', output or '')
            ok, msg, output = _run_simple_action_flow(process, collector, output, clean_num, exit_num, total_timeout_s)
            return RunResult(ok, msg, output or '')

        if mode == 'tests':
            tests_num = find_menu_number(output, ['Run Tests', 'Тест', 'Tests'])
            exit_num = find_menu_number(output, ['Exit', 'Выход', 'Quit', 'Close'])
            if not tests_num:
                kill_process(process)
                return RunResult(False, 'cannot parse Run Tests', output or '')
            ok, msg, output = _run_tests_flow(process, collector, output, tests_num, exit_num, strategy_name, cfgs or [], total_timeout_s, is_cancelled=is_cancelled)
            return RunResult(ok, msg, output or '')

        kill_process(process)
        return RunResult(False, 'unknown mode', output or '')
    finally:
        try:
            if process.stdout:
                process.stdout.close()
        except Exception:
            pass
        try:
            if process.stdin:
                process.stdin.close()
        except Exception:
            pass


def _run_simple_action_flow(process: subprocess.Popen, collector: PipeCollector, output: str, action_num: str, exit_num: str, total_timeout_s: float) -> tuple[bool, str, str]:
    write_stdin(process, f'{action_num}\r\n')
    started = time.monotonic()
    saw_prompt = False

    while True:
        output += collector.drain()

        if PRESS_ANY_KEY_RE.search(output):
            saw_prompt = True
            write_stdin(process, '\r\n')
            output = strip_press_any_key(output)
            menu_ready, output = _wait_main_menu(process, collector, output, 10.0)
            if menu_ready:
                if exit_num:
                    write_stdin(process, f'{exit_num}\r\n')
                wait_exit_or_timeout(process, collector, 20.0)
                output += collector.drain()
                if ERROR_RE.search(output):
                    return (False, 'error', output)
                return (True, 'ok', output)
            continue

        if process.poll() is not None:
            output += collector.drain()
            if ERROR_RE.search(output):
                return (False, f'exit code {process.returncode}', output)
            return (saw_prompt and process.returncode == 0, f'exit code {process.returncode}', output)

        if time.monotonic() - started > total_timeout_s:
            log.error('timeout %.2fs. output:\n%s', total_timeout_s, output if output else '<empty>')
            kill_process(process)
            output += collector.drain()
            if ERROR_RE.search(output):
                return (False, 'timeout', output)
            return (True, 'ok (forced close)', output)

        time.sleep(0.05)


def _run_remove_flow(process: subprocess.Popen, collector: PipeCollector, output: str, remove_num: str, exit_num: str, total_timeout_s: float) -> tuple[bool, str, str]:
    write_stdin(process, f'{remove_num}\r\n')
    delete_seen = False
    started = time.monotonic()

    while True:
        output += collector.drain()

        if DELETE_OK_RE.search(output):
            delete_seen = True
        if PRESS_ANY_KEY_RE.search(output):
            write_stdin(process, '\r\n')
            output = strip_press_any_key(output)
            continue
        if delete_seen:
            menu_ready, output = _wait_main_menu(process, collector, output, 10.0)
            if menu_ready:
                if exit_num:
                    write_stdin(process, f'{exit_num}\r\n')
                wait_exit_or_timeout(process, collector, 20.0)
                output += collector.drain()
                return (True, 'ok', output)

        if process.poll() is not None:
            output += collector.drain()
            if SERVICE_MISSING_RE.search(output):
                return (True, 'ok', output)
            if process.returncode == 0 and (not ERROR_RE.search(output)):
                return (True, f'exit code {process.returncode}', output)
            return (delete_seen and process.returncode == 0, f'exit code {process.returncode}', output)

        if time.monotonic() - started > total_timeout_s:
            log.error('timeout %.2fs. output:\n%s', total_timeout_s, output if output else '<empty>')
            kill_process(process)
            output += collector.drain()
            if delete_seen:
                return (True, 'ok (forced close after delete)', output)
            return (False, 'timeout', output)

        time.sleep(0.05)


def _run_tests_flow(
    process: subprocess.Popen,
    collector: PipeCollector,
    output: str,
    tests_num: str,
    exit_num: str,
    kind: str,
    configs: list[str],
    total_timeout_s: float,
    is_cancelled=None,
) -> tuple[bool, str, str]:
    test_type_num = '1' if kind == 'standard' else '2'
    need_configs = bool(configs)
    write_stdin(process, f'{tests_num}\r\n')
    started = time.monotonic()
    stage = 'await_type'
    cfg_map: dict[str, str] = {}
    queue = list(configs)
    sent: list[str] = []
    sent_zero = False

    while True:
        if is_cancelled and is_cancelled():
            output += collector.drain()
            kill_process(process)
            return (False, 'cancelled', output)

        output += collector.drain()
        low = output.lower().replace('\r', '')

        if PRESS_ANY_KEY_RE.search(output):
            write_stdin(process, '\r\n')
            output = strip_press_any_key(output)
            menu_ready, output = _wait_main_menu(process, collector, output, 15.0)
            if menu_ready and exit_num:
                write_stdin(process, f'{exit_num}\r\n')
            wait_exit_or_timeout(process, collector, 20.0)
            output += collector.drain()
            if ERROR_RE.search(output):
                return (False, 'error', output)
            return (True, 'ok', output)

        if stage == 'await_type' and TEST_TYPE_PROMPT_RE.search(output):
            write_stdin(process, f'{test_type_num}\r\n')
            stage = 'await_mode'
            continue

        if stage == 'await_mode' and TEST_MODE_PROMPT_RE.search(output):
            write_stdin(process, '2\r\n' if need_configs else '1\r\n')
            stage = 'await_cfgs' if need_configs else 'running'
            continue

        if stage == 'await_cfgs':
            if not cfg_map and ('available configs' in low or ('доступн' in low and 'config' in low)):
                cfg_map = parse_available_configs(output)
            if PROMPT_FILE_INDEX_RE.search(output) or PROMPT_SELECT_RE.search(output):
                if not cfg_map:
                    cfg_map = parse_available_configs(output)

                if (not sent) and (not sent_zero) and configs and ('enter numbers' in low or 'введите номер' in low or 'введите номера' in low):
                    idxs: list[str] = []
                    for cfg in configs:
                        target = normalize_strategy_name(cfg).lower()
                        idx = cfg_map.get(target) or cfg_map.get((target + '.bat').lower()) or find_strategy_number(output, target)
                        if idx:
                            idxs.append(idx)
                    uniq: list[str] = []
                    for idx in idxs:
                        if idx not in uniq:
                            uniq.append(idx)
                    if uniq:
                        sent_zero = True
                        queue.clear()
                        write_stdin(process, ','.join(uniq) + '\r\n')
                        stage = 'running'
                        continue

                if queue:
                    target = normalize_strategy_name(queue.pop(0)).lower()
                    idx = cfg_map.get(target) or cfg_map.get((target + '.bat').lower()) or find_strategy_number(output, target)
                    if not idx:
                        log.warning('tests: cannot map config "%s" to index', target)
                        continue
                    sent.append(target)
                    write_stdin(process, f'{idx}\r\n')
                    continue

                if not sent_zero:
                    sent_zero = True
                    write_stdin(process, '0\r\n')
                    stage = 'running'
                    continue

        if process.poll() is not None:
            output += collector.drain()
            if ERROR_RE.search(output):
                return (False, f'exit code {process.returncode}', output)
            return (process.returncode == 0, f'exit code {process.returncode}', output)

        if time.monotonic() - started > total_timeout_s:
            log.error('tests timeout %.2fs. output:\n%s', total_timeout_s, output if output else '<empty>')
            kill_process(process)
            output += collector.drain()
            return (False, 'timeout', output)

        time.sleep(0.05)


def _run_install_flow(
    process: subprocess.Popen,
    collector: PipeCollector,
    output: str,
    install_num: str,
    exit_num: str,
    strategy_name: str,
    total_timeout_s: float,
) -> tuple[bool, str, str]:
    write_stdin(process, f'{install_num}\r\n')
    started = time.monotonic()
    strategy_sent = False
    install_seen = False

    while True:
        output += collector.drain()

        if PRESS_ANY_KEY_RE.search(output):
            write_stdin(process, '\r\n')
            output = strip_press_any_key(output)
            continue

        if (not strategy_sent) and strategy_name and looks_like_strategy_menu(output):
            strat_num = find_strategy_number(output, strategy_name)
            if not strat_num:
                kill_process(process)
                output += collector.drain()
                return (False, f'cannot parse strategy "{strategy_name}"', output)
            write_stdin(process, f'{strat_num}\r\n')
            strategy_sent = True
            continue

        if INSTALL_OK_RE.search(output):
            install_seen = True

        if strategy_sent and ERROR_RE.search(output) and not install_seen:
            if PRESS_ANY_KEY_RE.search(output):
                write_stdin(process, '\r\n')
            menu_ready, output = _wait_main_menu(process, collector, output, 5.0)
            if menu_ready and exit_num:
                write_stdin(process, f'{exit_num}\r\n')
            wait_exit_or_timeout(process, collector, 10.0)
            output += collector.drain()
            return (False, 'install failed', output)

        if install_seen:
            menu_ready, output = _wait_main_menu(process, collector, output, 10.0)
            if menu_ready:
                if exit_num:
                    write_stdin(process, f'{exit_num}\r\n')
                wait_exit_or_timeout(process, collector, 20.0)
                output += collector.drain()
                return (True, 'ok', output)

        if strategy_sent and looks_like_main_menu(output) and (not ERROR_RE.search(output)):
            if exit_num:
                write_stdin(process, f'{exit_num}\r\n')
            wait_exit_or_timeout(process, collector, 20.0)
            output += collector.drain()
            return (True, 'ok', output)

        if process.poll() is not None:
            output += collector.drain()
            if strategy_sent and process.returncode == 0 and (not ERROR_RE.search(output)):
                return (True, f'exit code {process.returncode}', output)
            return (False, f'exit code {process.returncode}', output)

        if time.monotonic() - started > total_timeout_s:
            log.error('timeout %.2fs. output:\n%s', total_timeout_s, output if output else '<empty>')
            kill_process(process)
            output += collector.drain()
            if strategy_sent and (not ERROR_RE.search(output)):
                return (True, 'ok (forced close)', output)
            return (False, 'timeout', output)

        time.sleep(0.05)


def _wait_main_menu(process: subprocess.Popen, collector: PipeCollector, current: str, wait_s: float) -> tuple[bool, str]:
    started = time.monotonic()
    output = current or ''
    while time.monotonic() - started < wait_s:
        output += collector.drain()
        if looks_like_main_menu(output):
            return (True, output)
        if process.poll() is not None:
            return (False, output)
        time.sleep(0.05)
    return (False, output)


def _drain_output(collector: PipeCollector, emitter: LineEmitter, output: str) -> str:
    chunk = collector.drain()
    if not chunk:
        return output
    emitter.feed(chunk)
    return output + chunk
