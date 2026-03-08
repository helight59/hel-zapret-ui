import ctypes
import logging
import os
import re
import shutil
from pathlib import Path
try:
    import winreg  # type: ignore
except Exception:
    winreg = None  # type: ignore
from src.cli.process import run

log = logging.getLogger('service_fix')

_QC_BAD_RE = re.compile(r'(?is)\b1734\b|array bounds are invalid|неверные границы массива')

_DRIVE_REMOTE = 4
_DRIVE_UNKNOWN = 0
_DRIVE_NO_ROOT_DIR = 1


def ensure_service_config_readable(service_name: str, zapret_root: Path, wrapper_name: str = '_hel_zapret_run.cmd', max_len: int = 2048) -> tuple[bool, str]:
    ok, out = _qc_ok(service_name)
    img = _get_image_path(service_name)

    if ok and img and (not _needs_localize(img)):
        return True, 'ok'

    if not img:
        return False, 'cannot read ImagePath'

    try:
        local_root = _ensure_local_zapret_copy(zapret_root) if _needs_localize(img) else zapret_root
    except Exception as e:
        return False, f'cannot copy zapret locally: {e}'

    rewritten = _rewrite_imagepath(img, zapret_root, local_root)

    wrapper_path = _default_wrapper_path(wrapper_name)
    try:
        _write_wrapper(wrapper_path, rewritten)
    except Exception as e:
        return False, f'cannot write wrapper: {e}'

    new_img = _build_wrapper_imagepath(wrapper_path)
    try:
        _set_image_path(service_name, new_img)
    except Exception as e:
        return False, f'cannot update ImagePath: {e}'

    run(['sc.exe', 'stop', service_name])
    run(['sc.exe', 'start', service_name])

    ok2, out2 = _qc_ok(service_name)
    if ok2:
        if _needs_localize(img):
            return True, f'fixed via local copy + wrapper ({local_root})'
        if (len(img) > max_len) or _QC_BAD_RE.search(out or ''):
            return True, 'fixed via wrapper'
        return True, 'ok'

    tail = (out2 or '').strip()
    return False, f'wrapper applied but qc still fails: {tail[:300]}'


def _qc_ok(service_name: str) -> tuple[bool, str]:
    cmd = f'sc.exe qc {service_name} 2>&1 | Out-String'
    r = run(['powershell.exe', '-NoProfile', '-Command', cmd])
    out = (r.out or '').strip()
    if r.code == 0 and not _QC_BAD_RE.search(out):
        return True, out
    return False, out


def _svc_key(service_name: str) -> str:
    return r'SYSTEM\CurrentControlSet\Services\%s' % service_name


def _get_image_path(service_name: str) -> str:
    if winreg is None:
        return ''
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _svc_key(service_name), 0, winreg.KEY_READ) as k:
            v, _t = winreg.QueryValueEx(k, 'ImagePath')
            if isinstance(v, str):
                return v
    except Exception:
        log.exception('read ImagePath failed')
    return ''


def _set_image_path(service_name: str, value: str) -> None:
    if winreg is None:
        raise RuntimeError('winreg unavailable')
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _svc_key(service_name), 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, 'ImagePath', 0, winreg.REG_EXPAND_SZ, value)
    except Exception:
        log.exception('set ImagePath failed')
        raise


def _write_wrapper(path: Path, imagepath: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        '@echo off',
        'setlocal',
        imagepath,
        'exit /b %errorlevel%',
    ]
    raw = '\r\n'.join(lines) + '\r\n'
    b = raw.encode('ascii', errors='replace')
    with open(path, 'wb') as f:
        f.write(b)


def _build_wrapper_imagepath(wrapper_path: Path) -> str:
    p = str(wrapper_path)
    return f'cmd.exe /d /q /c ""{p}""'


def _default_wrapper_path(wrapper_name: str) -> Path:
    pd = os.environ.get('ProgramData') or r'C:\ProgramData'
    return Path(pd) / 'hel-zapret' / wrapper_name


def _ensure_local_zapret_copy(zapret_root: Path) -> Path:
    pd = os.environ.get('ProgramData') or r'C:\ProgramData'
    dest = Path(pd) / 'hel-zapret' / 'zapret'
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copytree(zapret_root, dest, dirs_exist_ok=True)
    return dest


def _rewrite_imagepath(img: str, zapret_root: Path, local_root: Path) -> str:
    src = str(zapret_root)
    dst = str(local_root)

    if src.endswith('\\') or src.endswith('/'):
        src = src[:-1]
    if dst.endswith('\\') or dst.endswith('/'):
        dst = dst[:-1]

    s = img
    s = s.replace(src + '\\', dst + '\\')
    s = s.replace(src + '/', dst + '\\')
    s = s.replace(src, dst)
    return s


def _needs_localize(img: str) -> bool:
    m = re.match(r'\s*"?([A-Za-z]:)\\', img)
    if not m:
        return False
    drive = m.group(1).upper() + r'\\'
    try:
        t = ctypes.windll.kernel32.GetDriveTypeW(drive)
        return t in (_DRIVE_UNKNOWN, _DRIVE_NO_ROOT_DIR, _DRIVE_REMOTE)
    except Exception:
        return False