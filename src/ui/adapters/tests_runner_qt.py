from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from src.services.tests.runner import RunOptions, run_tests


class TestsRunner(QObject):
    rowUpdated = Signal(int)
    progressUpdated = Signal(object)
    runFinished = Signal(str, str)
    runStarted = Signal()

    def __init__(self, zapret_dir: Path, data_dir: Path):
        super().__init__()
        self.zapret_dir = zapret_dir
        self.data_dir = data_dir
        self._thread: QThread | None = None
        self._worker: _Worker | None = None

    def start(self, opts: RunOptions) -> None:
        if self._thread:
            return
        self._thread = QThread()
        self._worker = _Worker(self.zapret_dir, self.data_dir, opts)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.rowUpdated.connect(self.rowUpdated.emit)
        self._worker.progressUpdated.connect(self.progressUpdated.emit)
        self._worker.finished.connect(self._on_finished)

        self.runStarted.emit()
        self._thread.start()

    def cancel(self) -> None:
        if self._worker:
            self._worker.cancel()

    def _on_finished(self, status: str, payload: str) -> None:
        if self._thread:
            self._thread.quit()
            self._thread.wait(500)
        self._thread = None
        self._worker = None
        self.runFinished.emit(status, payload)


class _Worker(QObject):
    rowUpdated = Signal(int)
    progressUpdated = Signal(object)
    finished = Signal(str, str)

    def __init__(self, zapret_dir: Path, data_dir: Path, opts: RunOptions):
        super().__init__()
        self.zapret_dir = zapret_dir
        self.data_dir = data_dir
        self.opts = opts
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        status, payload = run_tests(
            self.zapret_dir,
            self.data_dir,
            self.opts,
            on_row_updated=lambda i: self.rowUpdated.emit(i),
            on_progress=lambda ev: self.progressUpdated.emit(ev),
            is_cancelled=lambda: self._cancel,
        )
        self.finished.emit(status, payload)
