from __future__ import annotations

import logging
from typing import Callable, Any

from PySide6.QtCore import QObject, Signal


log = logging.getLogger('worker')


class StateWorker(QObject):
    done = Signal(object)
    error = Signal(str)

    def __init__(self, fn: Callable[[], Any]):
        super().__init__()
        self.fn = fn

    def run(self):
        try:
            self.done.emit(self.fn())
        except Exception as e:
            log.exception('StateWorker failed')
            self.error.emit(str(e))
