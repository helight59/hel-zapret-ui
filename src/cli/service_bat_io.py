import logging
import subprocess
import threading
import time


log = logging.getLogger('service_menu')
CREATE_NO_WINDOW = 0x08000000


class PipeCollector:
    def __init__(self, process: subprocess.Popen):
        self._process = process
        self._buf: list[str] = []
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        try:
            if not self._process.stdout:
                return
            while True:
                chunk = self._process.stdout.read(1)
                if chunk:
                    with self._lock:
                        self._buf.append(chunk)
                    continue
                if self._process.poll() is not None:
                    break
                time.sleep(0.01)
        except Exception:
            return

    def drain(self) -> str:
        with self._lock:
            if not self._buf:
                return ''
            chunk = ''.join(self._buf)
            self._buf.clear()
            return chunk


class LineEmitter:
    def __init__(self, callback):
        self._callback = callback
        self._buf = ''

    def feed(self, chunk: str) -> None:
        if not self._callback or not chunk:
            return
        self._buf += chunk
        while '\n' in self._buf:
            line, self._buf = self._buf.split('\n', 1)
            self._emit((line or '').rstrip('\r'))

    def flush(self) -> None:
        if not self._callback:
            self._buf = ''
            return
        tail = (self._buf or '').rstrip('\r')
        if tail:
            self._emit(tail)
        self._buf = ''

    def _emit(self, line: str) -> None:
        try:
            self._callback(line)
        except Exception:
            return


def write_stdin(process: subprocess.Popen, payload: str) -> None:
    try:
        if process.stdin:
            process.stdin.write(payload)
            process.stdin.flush()
    except Exception:
        log.exception('stdin write failed')


def wait_exit_or_timeout(process: subprocess.Popen, collector: PipeCollector, wait_s: float) -> None:
    started = time.monotonic()
    while time.monotonic() - started < wait_s:
        if process.poll() is not None:
            return
        collector.drain()
        time.sleep(0.05)


def kill_process(process: subprocess.Popen) -> None:
    try:
        if process.poll() is not None:
            return
        if process.pid:
            subprocess.run(
                ['taskkill', '/T', '/F', '/PID', str(process.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
            return
    except Exception:
        pass

    try:
        process.kill()
    except Exception:
        pass
