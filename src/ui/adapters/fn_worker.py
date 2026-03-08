from __future__ import annotations

import logging
from typing import Callable, Any

from PySide6.QtCore import QObject, Signal


log = logging.getLogger('worker')


class FnWorker(QObject):
    done = Signal(bool, str)

    def __init__(self, fn: Callable[[], Any]):
        super().__init__()
        self.fn = fn
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            r = self.fn()
            ok, msg = _unwrap(r)
            if self._cancel:
                self.done.emit(False, 'отменено')
                return
            self.done.emit(bool(ok), str(msg or ''))
        except Exception as e:
            log.exception('FnWorker failed')
            self.done.emit(False, str(e))


def _unwrap(v: Any) -> tuple[bool, str]:
    if v is None:
        return (True, '')
    if isinstance(v, tuple) and len(v) >= 2:
        return (bool(v[0]), str(v[1]))
    ok = getattr(v, 'ok', None)
    msg = getattr(v, 'message', None)
    if ok is not None and msg is not None:
        return (bool(ok), str(msg))
    return (True, str(v))
