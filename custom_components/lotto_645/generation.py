"""Measured regeneration progress. Percent is work completed, never win odds."""
from __future__ import annotations

from datetime import UTC, datetime
import math
from statistics import median
from time import monotonic
from typing import Callable
from uuid import uuid4


class GenerationCancelled(Exception):
    """Cooperative executor cancellation at a bounded candidate checkpoint."""


class GenerationProgress:
    """One job at a time; no personal profile or ticket data in timing storage."""

    def __init__(self, clock: Callable[[], float] = monotonic) -> None:
        self.clock = clock
        self.samples: dict[str, list[float]] = {}
        self.state = "idle"
        self.run_id: str | None = None
        self.started_at: str | None = None
        self.started = self.clock()
        self.elapsed_final = 0.0
        self.methods: dict[str, str] = {}
        self.phase = "idle"
        self.completed = 0
        self.current_method: str | None = None
        self.candidates_done = 0
        self.candidates_total = 0
        self.work_started: float | None = None
        self.work_fraction = 0.0
        self.worked = False
        self.error: str | None = None

    @property
    def active(self) -> bool:
        return self.state == "running"

    @property
    def key(self) -> str:
        return ",".join(sorted(self.methods))

    def load(self, raw: object) -> None:
        if raw is None:
            return
        if not isinstance(raw, dict) or raw.get("version") != 1 or not isinstance(raw.get("samples"), dict):
            raise ValueError("Invalid timing history")
        loaded = {}
        for key, values in list(raw["samples"].items())[-20:]:
            if not isinstance(key, str) or len(key) > 2000 or not isinstance(values, list):
                raise ValueError("Invalid timing sample")
            if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 < v <= 86400 for v in values):
                raise ValueError("Invalid timing duration")
            loaded[key] = values[-5:]
        self.samples = loaded

    def to_storage(self) -> dict:
        return {"version": 1, "samples": {k: list(v) for k, v in self.samples.items()}}

    def begin(self, methods: dict[str, str]) -> str:
        if self.active:
            return self.run_id
        self.run_id = uuid4().hex
        self.methods = dict(methods)
        self.state = "running"
        self.phase = "queued"
        self.started = self.clock()
        self.started_at = datetime.now(UTC).isoformat()
        self.completed = 0
        self.current_method = None
        self.candidates_done = self.candidates_total = 0
        self.work_started = None
        self.work_fraction = 0.0
        self.worked = False
        self.error = None
        return self.run_id

    def update(self, event: dict) -> None:
        if not self.active:
            return
        self.phase = event["phase"]
        if self.phase == "method_start":
            if self.work_started is None:
                self.work_started = self.clock()
            self.worked = True
            self.current_method = event["method_id"]
            self.completed = event["index"] - 1
            self.candidates_done = self.candidates_total = 0
        elif self.phase == "method_progress":
            self.candidates_done = event["candidates_done"]
            self.candidates_total = event["candidates_total"]
        elif self.phase == "method_complete":
            self.completed = event["index"]
            self.candidates_done = self.candidates_total = 0
        total = len(self.methods)
        within = self.candidates_done / self.candidates_total if self.candidates_total else 0
        self.work_fraction = max(self.work_fraction, min(1.0, (self.completed + within) / total)) if total else 0

    def finish(self, state: str, error: str | None = None) -> None:
        if not self.active:
            return
        self.elapsed_final = max(0.0, self.clock() - self.started)
        if state == "completed" and self.worked and self.completed == len(self.methods):
            self.samples[self.key] = (self.samples.get(self.key, []) + [max(.001, self.elapsed_final)])[-5:]
            while len(self.samples) > 20:
                del self.samples[next(iter(self.samples))]
        self.state = state
        self.phase = state
        self.error = error

    def view(self) -> dict:
        elapsed = max(0.0, self.clock() - self.started) if self.active else self.elapsed_final
        samples = self.samples.get(self.key, [])
        estimate = median(samples) if samples else None
        basis = "same_methods_local_history" if samples else "measuring"
        remaining = None
        overdue = False
        # After two completed methods, use actual work rate of THIS run too.
        if self.active and self.completed >= 2 and self.work_started is not None and 0 < self.work_fraction < 1:
            work_elapsed = max(0.0, self.clock() - self.work_started)
            remaining = work_elapsed * (1 - self.work_fraction) / self.work_fraction
            estimate = elapsed + remaining
            basis = "current_run_work_rate"
        elif self.active and estimate is not None:
            overdue = elapsed >= estimate
            remaining = None if overdue else estimate - elapsed
        if not self.active:
            remaining = None
        return {
            "state": self.state, "run_id": self.run_id, "phase": self.phase,
            "started_at": self.started_at, "elapsed_seconds": round(elapsed, 1),
            "completed_methods": self.completed, "total_methods": len(self.methods),
            "current_method_id": self.current_method,
            "current_method": self.methods.get(self.current_method, ""),
            "candidates_done": self.candidates_done, "candidates_total": self.candidates_total,
            "percent": 100 if self.state == "completed" else min(99, int(self.work_fraction * 100)),
            "estimated_total_seconds": round(estimate, 1) if estimate is not None else None,
            "estimated_remaining_seconds": round(remaining, 1) if remaining is not None else None,
            "estimate_basis": basis, "estimate_sample_count": len(samples),
            "estimate_exceeded": overdue, "error": self.error,
            "notice": "예상시간은 이 HA의 실행 기록/현재 처리속도 기반 추정입니다. 기기 부하·방식별 연산량에 따라 달라집니다. AI는 재생성하지 않습니다.",
        }


def progress_message(view: dict) -> str:
    states = {"idle": "대기", "completed": "완료", "error": "실패", "cancelled": "중단"}
    if view["state"] != "running":
        return f"{states.get(view['state'], view['state'])} · {view['elapsed_seconds']:.0f}초"
    phases = {"queued": "시작 대기", "history": "당첨 이력 확인", "restore": "기존 추천 복원", "features": "공통 지표 계산", "saving": "결과 저장", "ai": "설정된 자동 AI 작업"}
    stage = view["current_method"] if view["phase"].startswith("method_") else phases.get(view["phase"], "마무리")
    return f"{view['completed_methods']}/{view['total_methods']}개 완료 · {stage}"
