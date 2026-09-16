"""Versioned generation API. Evaluation and experiment storage belong to consumers."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict
from datetime import date
from hashlib import sha256
import json
from typing import Any

from . import API_VERSION, CORE_VERSION, MIN_HISTORY
from .analysis import build_analysis
from .methods import DEFAULT_METHOD_IDS, METHODS_BY_ID, method_catalog, consensus_source_ids
from .models import AnalysisResult, LottoDraw


def validate_method_ids(value: Sequence[str] | None = None) -> tuple[str, ...]:
    """Fail closed on unknown IDs; never silently substitute a different formula."""
    if value is None:
        return DEFAULT_METHOD_IDS
    if not isinstance(value, (list, tuple)) or not value or any(type(x) is not str for x in value):
        raise ValueError("공식 ID를 하나 이상 지정하세요")
    ids = tuple(dict.fromkeys(value))
    if len(ids) != len(value):
        raise ValueError("공식 ID가 중복되었습니다")
    unknown = set(ids) - METHODS_BY_ID.keys()
    if unknown:
        raise ValueError("지원하지 않는 공식: " + ", ".join(sorted(unknown)))
    if set(ids) & {"selected_median_consensus", "selected_vote_consensus"} and len(consensus_source_ids(ids)) < 2:
        raise ValueError("합의에는 다른 생성 공식 두 개 이상이 필요합니다")
    return ids


def describe() -> dict[str, Any]:
    """JSON catalog of the exact formulas used by both HA and Lotto Lab."""
    return {"api_version": API_VERSION, "core_version": CORE_VERSION,
            "python_requires": ">=3.11", "min_history": MIN_HISTORY,
            "game": {"min_number": 1, "max_number": 45, "pick": 6},
            "default_method_ids": list(DEFAULT_METHOD_IDS),
            "methods": [{**row, "formula_version": METHODS_BY_ID[row['method_id']].formula_version,
                         "requires_personal_profile": row['method_id'] == 'myungri_hetu_day_pillar'}
                        for row in method_catalog()],
            "capabilities": ["generate", "catalog", "progress"],
            "history_contract": "contiguous_prefix_from_round_1; target=last_round+1",
            "notice": "번호 생성 전용입니다. 과거 검증·채점·저장·네트워크는 소비 프로젝트의 책임입니다."}


def normalize_history(history: Sequence[LottoDraw | Mapping[str, Any]]) -> list[LottoDraw]:
    if not isinstance(history, (list, tuple)) or len(history) < MIN_HISTORY:
        raise ValueError(f"최소 {MIN_HISTORY}회 이력이 필요합니다")
    rows = []
    last_date = None
    for expected, raw in enumerate(history, 1):
        if isinstance(raw, Mapping):
            if type(raw.get("round")) is not int or type(raw.get("bonus")) is not int:
                raise ValueError("회차와 보너스는 정수여야 합니다")
            row = LottoDraw.from_storage(dict(raw))
        else:
            row = raw
        if not isinstance(row, LottoDraw) or type(row.round) is not int or row.round != expected:
            raise ValueError("1회부터 오름차순으로 연속된 이력만 허용합니다")
        # Recheck even direct dataclass instances; callers cannot bypass validation.
        if (len(row.numbers) != 6 or len(set(row.numbers)) != 6
                or any(type(n) is not int or not 1 <= n <= 45 for n in row.numbers)
                or tuple(sorted(row.numbers)) != tuple(row.numbers)
                or type(row.bonus) is not int or not 1 <= row.bonus <= 45 or row.bonus in row.numbers):
            raise ValueError("당첨번호 형식이 올바르지 않습니다")
        when = date.fromisoformat(row.draw_date)
        if when.isoformat() != row.draw_date:
            raise ValueError("날짜는 YYYY-MM-DD 형식이어야 합니다")
        if last_date is not None and when <= last_date:
            raise ValueError("추첨일은 회차 순서대로 증가해야 합니다")
        last_date = when
        rows.append(row)
    return rows


def generate(history: Sequence[LottoDraw | Mapping[str, Any]], method_ids: Sequence[str] | None = None,
             *, target_round: int | None = None, generation_nonce: int = 0,
             formula_options: dict | None = None, saju_profile: dict | None = None,
             excluded_combinations=(), restored_tickets=None, rng=None,
             progress_callback=None, recommendation_callback=None) -> AnalysisResult:
    """Generate only the draw immediately following the supplied history.

    This API never accepts the target's answer or fetches additional history.
    Reproducibility requires the same core, ordered methods, inputs and RNG.
    Production callers omit rng and use the operating-system CSPRNG.
    """
    rows = normalize_history(history)
    ids = validate_method_ids(method_ids)
    if target_round is not None and (type(target_round) is not int or target_round != rows[-1].round + 1):
        raise ValueError("대상 회차는 전달한 마지막 회차 바로 다음이어야 합니다")
    if type(generation_nonce) is not int or generation_nonce < 0:
        raise ValueError("생성 순번은 0 이상의 정수여야 합니다")
    return build_analysis(rows, ids, generation_nonce, saju_profile, excluded_combinations,
                          restored_tickets, formula_options, rng=rng, progress_callback=progress_callback, recommendation_callback=recommendation_callback)


def generate_json(history, method_ids=None, **options) -> dict[str, Any]:
    """JSON-safe adapter for CLI/other-language consumers; not a test runner."""
    result = generate(history, method_ids, **options)
    return {"api_version": API_VERSION, "core_version": CORE_VERSION,
            "target_round": result.target_round, "based_on_round": result.based_on_round,
            "recommendations": [r.to_storage() for r in result.recommendations], "summary": result.summary}
