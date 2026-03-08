import json
import uuid
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class StrategyResult:
    name: str
    batch: str
    standard: str
    dpi: str
    duration_s: float
    log_standard: str
    log_dpi: str

    std_http_ok: int = 0
    std_http_err: int = 0
    std_http_unsup: int = 0
    std_ping_ok: int = 0
    std_ping_fail: int = 0

    dpi_ok: int = 0
    dpi_fail: int = 0
    dpi_unsup: int = 0
    dpi_blocked: int = 0

    best_standard: bool = False
    best_dpi: bool = False


@dataclass
class TestRun:
    run_id: str
    started_at: str
    finished_at: str
    zapret_version_local: str
    standard_enabled: bool
    dpi_enabled: bool
    selected_strategies: list[str]
    results: list[StrategyResult]
    pdf_path: str
    restore: dict[str, Any]


class HistoryStore:
    def __init__(self, data_dir: Path):
        self.base = data_dir / 'history'
        self.base.mkdir(parents=True, exist_ok=True)

    def new_run_dir(self) -> Path:
        run_id = uuid.uuid4().hex
        d = self.base / run_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_run(self, run_dir: Path, run: TestRun) -> None:
        (run_dir / 'run.json').write_text(json.dumps(asdict(run), ensure_ascii=False, indent=2), encoding='utf-8')

    def list_runs(self) -> list[tuple[str, Path]]:
        items = []
        for d in sorted(self.base.glob('*'), key=lambda p: p.name, reverse=True):
            if (d / 'run.json').exists():
                items.append((d.name, d))
        return items

    def read_run(self, run_dir: Path) -> dict[str, Any]:
        p = run_dir / 'run.json'
        return json.loads(p.read_text(encoding='utf-8'))
