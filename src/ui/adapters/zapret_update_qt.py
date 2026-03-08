from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from src.services.zapret.service import ZapretService


class ZapretUpdateWorker(QObject):
    progress = Signal(int)
    stage = Signal(str)
    done = Signal(bool, str)

    def __init__(self, zapret_dir: Path, data_dir: Path, version_tag: str = 'latest'):
        super().__init__()
        self.zapret_dir = zapret_dir
        self.data_dir = data_dir
        self.version_tag = version_tag
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            svc = ZapretService(self.zapret_dir, self.data_dir)
            r = svc.install_or_update_zapret(
                version_tag=self.version_tag,
                on_progress=lambda v: self.progress.emit(max(0, min(100, int(v)))),
                on_stage=lambda t: self.stage.emit(t),
                cancel_check=lambda: self._cancel,
            )
            self.done.emit(r.ok, r.message)
        except Exception as e:
            self.done.emit(False, str(e))
