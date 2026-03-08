from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StdTargetResult:
    target: str
    http: str | None
    tls12: str | None
    tls13: str | None
    ping_ms: int | None


@dataclass(frozen=True)
class StdAnalyticsRow:
    config: str
    ok: int
    err: int
    unsup: int
    ping_ok: int
    ping_fail: int

    def http_total(self) -> int:
        return self.ok + self.err + self.unsup

    def http_rate(self) -> str:
        total = self.http_total()
        if total <= 0:
            return '-'
        return f'{round((self.ok / total) * 100)}%'

    def ping_total(self) -> int:
        return self.ping_ok + self.ping_fail

    def ping_rate(self) -> str:
        total = self.ping_total()
        if total <= 0:
            return '-'
        return f'{round((self.ping_ok / total) * 100)}%'


@dataclass(frozen=True)
class DpiAnalyticsRow:
    config: str
    ok: int
    fail: int
    unsup: int
    blocked: int

    def total(self) -> int:
        return self.ok + self.fail + self.unsup + self.blocked

    def ok_rate(self) -> str:
        total = self.total()
        if total <= 0:
            return '-'
        return f'{round((self.ok / total) * 100)}%'


@dataclass
class DpiTargetRow:
    target_id: str
    provider: str
    http: str | None = None
    tls12: str | None = None
    tls13: str | None = None
