"""Selectable recommendation method catalog for Lotto 6/45.

The entries described as public formulas are commonly published filtering or
ranking heuristics. They are not mathematical prediction formulas and do not
change the probability of an individual six-number combination.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class MethodDefinition:
    """One deterministic recommendation profile."""

    method_id: str
    label: str
    category: str
    description: str
    weights: dict[str, float]
    pair_weight: float = 0.0
    diversity_weight: float = 0.0
    balance_weight: float = 0.0
    delta_weight: float = 0.0
    carryover_weight: float = 0.0
    pool_size: int = 22


METHOD_PHASE_RESIDUAL: Final = "phase_residual_graph"
METHOD_TRANSITION_GAP: Final = "transition_gap_phase"
METHOD_WEIGHTED_FREQUENCY: Final = "weighted_frequency"
METHOD_HOT_NUMBERS: Final = "hot_numbers"
METHOD_OVERDUE_GAP: Final = "overdue_gap"
METHOD_PAIR_COOCCURRENCE: Final = "pair_cooccurrence"
METHOD_BALANCE: Final = "balance_formula"
METHOD_DELTA: Final = "delta_system"
METHOD_CARRYOVER: Final = "carryover_formula"
METHOD_PUBLIC_ENSEMBLE: Final = "public_ensemble"

METHODS: Final[tuple[MethodDefinition, ...]] = (
    MethodDefinition(
        METHOD_PHASE_RESIDUAL,
        "독창 패턴 ①",
        "독창 분석",
        "장기·단기 잔차의 방향 전환, 변화 속도, 다음 회차 전이와 번호쌍 그래프를 결합합니다.",
        {
            "counter_phase": 0.34,
            "phase_velocity": 0.23,
            "transition": 0.20,
            "curvature": 0.13,
            "gap_surprise": 0.10,
        },
        pair_weight=0.20,
        diversity_weight=0.10,
    ),
    MethodDefinition(
        METHOD_TRANSITION_GAP,
        "독창 패턴 ②",
        "독창 분석",
        "최신 번호가 과거에 나온 뒤의 다음 회차 전이와 미출현 간격 위상을 중심으로 계산합니다.",
        {
            "transition": 0.31,
            "curvature": 0.24,
            "gap_surprise": 0.18,
            "counter_phase": 0.17,
            "long_neutral": 0.10,
        },
        pair_weight=0.17,
        diversity_weight=0.12,
    ),
    MethodDefinition(
        METHOD_WEIGHTED_FREQUENCY,
        "공개 공식 · 가중 빈도",
        "공개 분석식",
        "최근 10·30·100회와 전체 출현 빈도를 서로 다른 비중으로 합산하는 공개형 가중 빈도식입니다.",
        {
            "frequency_10": 0.34,
            "frequency_30": 0.28,
            "frequency_100": 0.23,
            "frequency_long": 0.15,
        },
        pair_weight=0.08,
        balance_weight=0.10,
        diversity_weight=0.06,
    ),
    MethodDefinition(
        METHOD_HOT_NUMBERS,
        "공개 공식 · 핫넘버",
        "공개 분석식",
        "아주 최근 구간에서 출현 강도가 상승한 번호를 우선하되 한 구간 쏠림은 감점합니다.",
        {
            "frequency_10": 0.44,
            "frequency_30": 0.34,
            "phase_velocity_positive": 0.22,
        },
        pair_weight=0.10,
        balance_weight=0.08,
        diversity_weight=0.05,
    ),
    MethodDefinition(
        METHOD_OVERDUE_GAP,
        "공개 공식 · 콜드·미출현",
        "공개 분석식",
        "번호별 현재 미출현 간격을 사용하되 지나친 장기 미출현수 집중을 완화한 콜드넘버 방식입니다.",
        {
            "overdue_capped": 0.48,
            "gap_surprise": 0.22,
            "long_neutral": 0.18,
            "recent_neutral": 0.12,
        },
        pair_weight=0.07,
        balance_weight=0.10,
        diversity_weight=0.08,
    ),
    MethodDefinition(
        METHOD_PAIR_COOCCURRENCE,
        "공개 공식 · 동반출현쌍",
        "공개 분석식",
        "전체 회차와 최근 120회에서 함께 나온 번호쌍의 기대값 대비 잔차를 결합합니다.",
        {
            "graph_strength": 0.52,
            "frequency_100": 0.18,
            "transition": 0.16,
            "gap_balance": 0.14,
        },
        pair_weight=0.30,
        balance_weight=0.06,
    ),
    MethodDefinition(
        METHOD_BALANCE,
        "공개 공식 · 균형 필터",
        "공개 분석식",
        "번호합, 홀짝, 저·고, 구간 분산을 역사적 중심 구간에 가깝게 맞추는 필터입니다.",
        {
            "long_neutral": 0.32,
            "recent_neutral": 0.28,
            "gap_balance": 0.22,
            "frequency_100": 0.18,
        },
        pair_weight=0.05,
        balance_weight=0.36,
        diversity_weight=0.10,
        pool_size=24,
    ),
    MethodDefinition(
        METHOD_DELTA,
        "공개 공식 · 델타 시스템",
        "공개 분석식",
        "오름차순 번호 사이 간격의 크기·반복·전체 범위를 평가하는 공개 델타 필터입니다.",
        {
            "long_neutral": 0.30,
            "recent_neutral": 0.24,
            "gap_balance": 0.20,
            "frequency_100": 0.16,
            "graph_strength": 0.10,
        },
        pair_weight=0.05,
        balance_weight=0.12,
        delta_weight=0.38,
        diversity_weight=0.08,
        pool_size=24,
    ),
    MethodDefinition(
        METHOD_CARRYOVER,
        "공개 공식 · 이월수",
        "공개 분석식",
        "직전 회차 번호가 다음 회차에 1~2개 다시 등장하는 경우를 우선하는 공개 이월수 규칙입니다.",
        {
            "transition": 0.34,
            "frequency_30": 0.23,
            "gap_balance": 0.18,
            "graph_strength": 0.15,
            "long_neutral": 0.10,
        },
        pair_weight=0.10,
        balance_weight=0.08,
        carryover_weight=0.34,
        diversity_weight=0.05,
    ),
    MethodDefinition(
        METHOD_PUBLIC_ENSEMBLE,
        "공식 탐색 ③ · 공개공식 종합형",
        "추천 공개 분석식",
        "가중 빈도·미출현 간격·동반출현쌍·균형·델타·이월수를 과도한 한 요소 없이 합의 점수로 결합합니다.",
        {
            "frequency_10": 0.10,
            "frequency_30": 0.13,
            "frequency_100": 0.13,
            "frequency_long": 0.08,
            "overdue_capped": 0.10,
            "transition": 0.12,
            "graph_strength": 0.14,
            "long_neutral": 0.05,
            "gap_balance": 0.05,
        },
        pair_weight=0.16,
        balance_weight=0.16,
        delta_weight=0.12,
        carryover_weight=0.10,
        diversity_weight=0.10,
        pool_size=24,
    ),
)

METHODS_BY_ID: Final = {method.method_id: method for method in METHODS}

DEFAULT_METHOD_IDS: Final[tuple[str, ...]] = (
    METHOD_PHASE_RESIDUAL,
    METHOD_TRANSITION_GAP,
    METHOD_WEIGHTED_FREQUENCY,
    METHOD_PAIR_COOCCURRENCE,
    METHOD_PUBLIC_ENSEMBLE,
)

PUBLIC_METHOD_IDS: Final[tuple[str, ...]] = tuple(
    method.method_id for method in METHODS if method.category != "독창 분석"
)


def normalize_method_ids(value: object) -> tuple[str, ...]:
    """Validate, deduplicate, and preserve the configured method order."""
    if not isinstance(value, (list, tuple)):
        return DEFAULT_METHOD_IDS
    result: list[str] = []
    for item in value:
        method_id = str(item)
        if method_id in METHODS_BY_ID and method_id not in result:
            result.append(method_id)
    return tuple(result) or DEFAULT_METHOD_IDS


def method_selector_options() -> list[dict[str, str]]:
    """Return options suitable for a Home Assistant multi-select selector."""
    return [
        {
            "value": method.method_id,
            "label": f"{method.label} — {method.description}",
        }
        for method in METHODS
    ]
