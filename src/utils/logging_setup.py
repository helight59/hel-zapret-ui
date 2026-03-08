from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path


_DEFAULT_FMT = '%(asctime)s %(levelname)s %(name)s: %(message)s'
_DEFAULT_DATEFMT = '%Y-%m-%d %H:%M:%S'


class TruncateFilter(logging.Filter):
    def __init__(self, max_len: int = 12000):
        super().__init__()
        self.max_len = int(max_len)

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
            if msg and len(msg) > self.max_len:
                cut = len(msg) - self.max_len
                record.msg = msg[:self.max_len] + f'… [truncated {cut} chars]'
                record.args = ()
        except Exception:
            pass
        return True


def create_file_handler(log_path: Path, level: int = logging.DEBUG) -> logging.Handler:
    h = RotatingFileHandler(str(log_path), maxBytes=2 * 1024 * 1024, backupCount=5, encoding='utf-8')
    h.setLevel(level)
    h.setFormatter(logging.Formatter(_DEFAULT_FMT, _DEFAULT_DATEFMT))
    h.addFilter(TruncateFilter())
    return h


def _quiet_noisy_loggers() -> None:
    for name in ('asyncio', 'urllib3', 'charset_normalizer', 'PIL'):
        try:
            logging.getLogger(name).setLevel(logging.WARNING)
        except Exception:
            pass


def _install_exception_hooks() -> None:
    base = getattr(sys, 'excepthook', None)

    def _sys_hook(exc_type, exc, tb):
        try:
            logging.getLogger('crash').critical('unhandled exception', exc_info=(exc_type, exc, tb))
        except Exception:
            pass
        if callable(base):
            try:
                base(exc_type, exc, tb)
            except Exception:
                pass

    sys.excepthook = _sys_hook

    if hasattr(threading, 'excepthook'):
        base_th = threading.excepthook

        def _th_hook(args):
            try:
                logging.getLogger('crash').critical(
                    'unhandled thread exception',
                    exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
                )
            except Exception:
                pass
            try:
                base_th(args)
            except Exception:
                pass

        threading.excepthook = _th_hook


def setup_logging(cfg) -> None:
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    for h in list(root.handlers):
        try:
            root.removeHandler(h)
            h.close()
        except Exception:
            pass

    data_dir = Path(cfg.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    log_path = data_dir / 'app.log'

    root.addHandler(create_file_handler(log_path))
    logging.captureWarnings(True)
    _quiet_noisy_loggers()
    _install_exception_hooks()

    logging.getLogger('app').info('logging initialized; file=%s', str(log_path))
