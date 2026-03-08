import logging
import os
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path
import datetime as dt
from typing import Callable, Optional
from src.app.config import AppConfig
from src.services.zapret.game_filter import write_game_filter_mode
from src.cli.process import run
from src.services.zapret.cleanup import remove_winws_services, kill_processes
from src.cli.service_bat import remove_services, install_service
from src.services.zapret.layout import ZapretLayout
from src.services.zapret.service_fix import ensure_service_config_readable
from src.cli.tests_patch import ensure_tests_cli_support
from src.services.zapret.user_lists import sync_saved_user_lists
from src.services.updater.release_catalog import resolve_zip_asset

log = logging.getLogger('updater')

ProgressFn = Callable[[int], None]
StageFn = Callable[[str], None]

class ZapretUpdater:
    def __init__(self, zapret_dir: Path, data_dir: Path, log_path: Optional[Path] = None):
        self.zapret_dir = zapret_dir
        self.data_dir = data_dir
        self.log_path = log_path or (Path(data_dir) / 'app.log')

    def update(self, version_tag: str = 'latest', on_progress: ProgressFn | None = None, on_stage: StageFn | None = None) -> tuple[bool, str]:
        p = on_progress or (lambda _: None)
        s = on_stage or (lambda _: None)
        try:
            log.info('update start zapret_dir=%s data_dir=%s', str(self.zapret_dir), str(self.data_dir))

            s('Остановка других обходов')
            log.info('cleanup: remove winws services + kill winws.exe/goodbyedpi.exe')
            remove_winws_services(exclude={'zapret'})
            kill_processes(['winws.exe', 'goodbyedpi.exe'])

            s('Остановка WinDivert')
            _stop_delete_windivert()

            # Critical: remove/stop the current zapret service BEFORE touching the folder.
            # Otherwise winws.exe keeps handles open and Windows refuses to delete/replace the directory.
            if self.zapret_dir.exists():
                s('Удаление старой версии zapret через service.bat')
                try:
                    log.info('service.bat remove (pre-delete)')
                    rr = remove_services(self.zapret_dir, parse_wait_s=0.0, menu_wait_s=25.0, total_timeout_s=120.0)
                    log.info('service.bat remove result ok=%s msg=%s', str(rr.ok), rr.message)
                    if not rr.ok:
                        log.warning('service.bat remove failed output:\n%s', rr.output if rr.output else '<empty>')
                except Exception:
                    log.exception('service.bat remove (pre-delete) failed')

                _best_effort_stop_zapret_service()
                log.info('post-remove: kill winws.exe/goodbyedpi.exe')
                kill_processes(['winws.exe', 'goodbyedpi.exe'])

            tag = (version_tag or 'latest').strip() or 'latest'
            latest = self._latest_version()
            label = _display_version(tag, latest)
            log.info('requested version tag: %s label=%s', tag, label)

            asset = resolve_zip_asset(tag)
            if not asset:
                log.error('zip asset not found')
                return False, f'не найден zip asset для релиза {tag}'
            log.info('download url: %s', asset)

            tmp = Path(tempfile.mkdtemp(prefix='zapret_upd_'))
            zip_path = tmp / 'zapret.zip'

            s('Скачивание zapret')
            self._download(asset, zip_path, p)
            log.info('downloaded: %s (%s bytes)', str(zip_path), str(zip_path.stat().st_size if zip_path.exists() else 0))

            s('Распаковка')
            stage = tmp / 'stage'
            stage.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, 'r') as z:
                names = z.namelist()
                total = max(len(names), 1)
                for i, name in enumerate(names):
                    z.extract(name, stage)
                    p(int((i + 1) * 100 / total))

            root = _find_zapret_root(stage)
            if not root:
                log.error('cannot detect zapret root in zip stage=%s', str(stage))
                return False, 'не удалось распознать корень в zip'
            log.info('detected zapret root: %s', str(root))

            backup_dir = Path(self.data_dir) / 'backup' / f'zapret_{dt.datetime.now().strftime("%Y%m%d_%H%M%S")}'
            backup_dir.mkdir(parents=True, exist_ok=True)
            log.info('backup dir: %s', str(backup_dir))

            user_lists = _collect_user_lists(self.zapret_dir)

            if self.zapret_dir.exists():
                s('Бэкап текущего zapret')
                log.info('backup current zapret from %s', str(self.zapret_dir))
                shutil.copytree(self.zapret_dir, backup_dir / 'zapret', dirs_exist_ok=True)
            else:
                log.info('no existing zapret dir; skip backup')

            s('Установка файлов')
            if self.zapret_dir.exists():
                log.info('remove old zapret dir: %s', str(self.zapret_dir))
                _safe_rmtree(self.zapret_dir)

            log.info('copy new zapret into: %s', str(self.zapret_dir))
            shutil.copytree(root, self.zapret_dir, dirs_exist_ok=True)
            _restore_user_lists(self.zapret_dir, user_lists)
            try:
                cfg = AppConfig.load(self.data_dir)
                synced = write_game_filter_mode(self.zapret_dir, cfg.game_filter_mode)
                log.info('game filter sync mode=%s ok=%s', cfg.game_filter_mode, str(synced))
            except Exception:
                log.exception('game filter sync failed')

            try:
                synced_lists = sync_saved_user_lists(self.zapret_dir, self.data_dir)
                log.info('user lists sync ok=%s', str(synced_lists))
            except Exception:
                log.exception('user lists sync failed')

            ok_patch, msg_patch = ensure_tests_cli_support(self.zapret_dir)
            log.info('tests cli patch ok=%s msg=%s', str(ok_patch), str(msg_patch))
            if not ok_patch:
                log.warning('tests cli patch failed: %s', str(msg_patch))

            s('Установка новой службы через service.bat')
            lay = ZapretLayout(self.zapret_dir)
            strategies = lay.list_strategies()
            if not strategies:
                log.error('no strategies found in zapret root: %s', str(self.zapret_dir))
                return False, 'в папке zapret не найдено ни одной стратегии (*.bat)'

            strategy = strategies[0]
            log.info('auto-selected strategy: %s', strategy)

            ir = install_service(self.zapret_dir, strategy, parse_wait_s=0.0, menu_wait_s=25.0, total_timeout_s=180.0)
            log.info('service.bat install result ok=%s msg=%s', str(ir.ok), ir.message)
            if not ir.ok:
                log.error('service.bat install failed output:\n%s', ir.output if ir.output else '<empty>')
                return False, 'служба не установилась (см. app.log)'

            s('Проверка службы')
            ok_fix, msg_fix = ensure_service_config_readable('zapret', self.zapret_dir)
            log.info('service fix result ok=%s msg=%s', str(ok_fix), msg_fix)
            if not ok_fix:
                return False, f'служба установилась, но конфиг некорректный: {msg_fix}'

            p(100)
            log.info('update done')
            return True, f'установлено/обновлено: {label}'
        except Exception:
            log.exception('update failed')
            return False, 'update failed (см. app.log)'

    def _latest_version(self) -> str:
        url = 'https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/main/.service/version.txt'
        try:
            return urllib.request.urlopen(url, timeout=10).read().decode('utf-8', errors='ignore').strip()
        except Exception:
            return ''

    def _download(self, url: str, dest: Path, on_progress: ProgressFn) -> None:
        req = urllib.request.Request(url, headers={'User-Agent': 'hel-zapret-ui'})
        with urllib.request.urlopen(req, timeout=60) as r:
            total = int(r.headers.get('Content-Length') or '0')
            read = 0
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, 'wb') as f:
                while True:
                    chunk = r.read(1024 * 256)
                    if not chunk:
                        break
                    f.write(chunk)
                    read += len(chunk)
                    if total > 0:
                        on_progress(min(100, int(read * 100 / total)))


def _display_version(tag: str, latest_version: str) -> str:
    t = (tag or '').strip() or 'latest'
    lv = (latest_version or '').strip()
    if t.lower() == 'latest':
        return lv or 'latest'
    if t.lower().startswith('v') and len(t) > 1:
        return t[1:]
    return t

def _stop_delete_windivert() -> None:
    for svc in ['WinDivert', 'WinDivert14']:
        run(['sc.exe', 'stop', svc])
        run(['sc.exe', 'delete', svc])

def _safe_rmtree(path: Path) -> None:
    if not path.exists():
        return

    # Windows is very sensitive to open handles. Even after killing winws.exe the directory
    # can stay locked for a short time. We do retries + accept a leftover EMPTY root dir.
    last_err: Exception | None = None
    for i, sleep_s in enumerate([0.0, 0.2, 0.6, 1.2, 2.0, 3.0]):
        if sleep_s > 0:
            try:
                import time
                time.sleep(sleep_s)
            except Exception:
                pass
        try:
            shutil.rmtree(path, onerror=_on_rm_error)
            return
        except Exception as e:
            last_err = e
            _best_effort_stop_zapret_service()
            _stop_delete_windivert()
            try:
                from src.services.zapret.cleanup import kill_processes
                kill_processes(['winws.exe', 'goodbyedpi.exe'])
            except Exception:
                pass
            try:
                # If only the root directory is locked, but it's already empty, we can continue.
                if path.exists() and (not any(path.iterdir())):
                    log.warning('rmtree: root dir locked but empty; continue: %s', str(path))
                    return
            except Exception:
                pass

    if last_err:
        raise last_err

def _on_rm_error(func, p, exc_info):
    try:
        os.chmod(p, 0o700)
        func(p)
    except Exception:
        raise


def _best_effort_stop_zapret_service() -> None:
    try:
        run(['sc.exe', 'stop', 'zapret'])
    except Exception:
        pass
    try:
        run(['sc.exe', 'stop', 'zapret3'])
    except Exception:
        pass

def _find_zapret_root(stage: Path) -> Path | None:
    candidates = [stage]
    candidates += [p for p in stage.iterdir() if p.is_dir()]
    for c in candidates:
        if (c / 'bin' / 'winws.exe').exists() and (c / 'lists').exists() and (c / 'utils').exists():
            return c
    for c in candidates:
        for d in c.rglob('*'):
            if d.is_dir() and (d / 'bin' / 'winws.exe').exists() and (d / 'lists').exists() and (d / 'utils').exists():
                return d
    return None

def _collect_user_lists(zapret_dir: Path) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    lists = zapret_dir / 'lists'
    if not lists.exists():
        return out
    for p in lists.glob('*-user.txt'):
        try:
            out[p.name] = p.read_bytes()
        except Exception:
            pass
    return out

def _restore_user_lists(zapret_dir: Path, data: dict[str, bytes]) -> None:
    if not data:
        return
    lists = zapret_dir / 'lists'
    lists.mkdir(parents=True, exist_ok=True)
    for name, b in data.items():
        try:
            (lists / name).write_bytes(b)
        except Exception:
            pass