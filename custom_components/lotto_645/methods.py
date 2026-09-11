"""Selectable recommendation method catalog for Lotto 6/45.

All methods are deterministic heuristic ranking/filtering profiles. They do not
change the mathematical probability of an individual six-number combination.
Traditional metaphysics is included as a reproducible cultural heuristic only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class MethodDefinition:
    """One recommendation profile."""

    method_id: str
    label: str
    category: str
    description: str
    weights: dict[str, float]
    pair_weight: float = 0.0
    triplet_weight: float = 0.0
    diversity_weight: float = 0.0
    balance_weight: float = 0.0
    delta_weight: float = 0.0
    carryover_weight: float = 0.0
    myungri_weight: float = 0.0
    pool_size: int = 22


METHOD_PHASE_RESIDUAL: Final = "phase_residual_graph"
METHOD_TRANSITION_GAP: Final = "transition_gap_phase"
METHOD_MULTISCALE_RESONANCE: Final = "multiscale_resonance"
METHOD_WEIGHTED_FREQUENCY: Final = "weighted_frequency"
METHOD_HOT_NUMBERS: Final = "hot_numbers"
METHOD_OVERDUE_GAP: Final = "overdue_gap"
METHOD_PAIR_COOCCURRENCE: Final = "pair_cooccurrence"
METHOD_TRIPLET_COOCCURRENCE: Final = "triplet_cooccurrence"
METHOD_RECENCY_DECAY: Final = "recency_decay"
METHOD_BAYESIAN_SHRINKAGE: Final = "bayesian_shrinkage"
METHOD_CYCLE_RHYTHM: Final = "cycle_rhythm"
METHOD_BALANCE: Final = "balance_formula"
METHOD_DELTA: Final = "delta_system"
METHOD_CARRYOVER: Final = "carryover_formula"
METHOD_PUBLIC_ENSEMBLE: Final = "public_ensemble"
METHOD_MYUNGRI_HETU: Final = "myungri_hetu_day_pillar"

METHODS: Final[tuple[MethodDefinition, ...]] = (
    MethodDefinition(
        METHOD_PHASE_RESIDUAL,
        "독창 패턴 · 위상잔차 그래프",
        "독창 분석",
        "전체 장기 빈도와 최근 변화 방향이 서로 엇갈리는 번호를 찾고, 변화 속도·다음 회차 전이·번호쌍 연결을 함께 평가합니다. 단순 핫/콜드 빈도 추종보다 여러 시간축의 방향 차이를 중시합니다.",
        {"counter_phase": 0.34, "phase_velocity": 0.23, "transition": 0.20, "curvature": 0.13, "gap_surprise": 0.10},
        pair_weight=0.20,
        diversity_weight=0.10,
    ),
    MethodDefinition(
        METHOD_TRANSITION_GAP,
        "독창 패턴 · 전이·간격 위상",
        "독창 분석",
        "직전 당첨번호가 과거에 나온 뒤 다음 회차에서 어떤 번호가 뒤따랐는지와 현재 미출현 간격의 위치를 결합합니다. 최근 변화의 굴곡과 장기 극단값도 함께 보정합니다.",
        {"transition": 0.31, "curvature": 0.24, "gap_surprise": 0.18, "counter_phase": 0.17, "long_neutral": 0.10},
        pair_weight=0.17,
        diversity_weight=0.12,
    ),
    MethodDefinition(
        METHOD_MULTISCALE_RESONANCE,
        "독창 패턴 · 다중시간대 공명",
        "독창 분석",
        "최근 10·30·120·260회와 전체 구간의 변화가 동시에 강하게 나타나는 번호를 찾습니다. 전이·그래프·간격을 보조로 사용해 한 구간의 일시적 급등에만 끌려가지 않도록 구성했습니다.",
        {"phase_velocity": 0.22, "curvature": 0.19, "counter_phase": 0.18, "transition": 0.16, "graph_strength": 0.15, "gap_balance": 0.10},
        pair_weight=0.16,
        diversity_weight=0.13,
        balance_weight=0.08,
    ),
    MethodDefinition(
        METHOD_WEIGHTED_FREQUENCY,
        "공개 공식 · 가중 빈도",
        "공개 분석식",
        "최근 10·30·100회와 전체 출현 빈도에 서로 다른 비중을 주는 방식입니다. 최근성은 반영하지만 장기 통계도 남겨 특정 짧은 구간에 과도하게 맞추지 않습니다.",
        {"frequency_10": 0.34, "frequency_30": 0.28, "frequency_100": 0.23, "frequency_long": 0.15},
        pair_weight=0.08,
        balance_weight=0.10,
        diversity_weight=0.06,
    ),
    MethodDefinition(
        METHOD_HOT_NUMBERS,
        "공개 공식 · 핫넘버",
        "공개 분석식",
        "최근 10·30회에서 출현이 늘고 있는 번호를 우선하는 전형적인 핫넘버 방식입니다. 번호대와 조합 내부 연결을 함께 보정해 최근 번호만 과도하게 몰리는 현상을 줄입니다.",
        {"frequency_10": 0.44, "frequency_30": 0.34, "phase_velocity_positive": 0.22},
        pair_weight=0.10,
        balance_weight=0.08,
        diversity_weight=0.05,
    ),
    MethodDefinition(
        METHOD_OVERDUE_GAP,
        "공개 공식 · 콜드·미출현",
        "공개 분석식",
        "현재까지 나오지 않은 회차 간격이 긴 번호를 우선하는 콜드넘버 방식입니다. 극단적으로 오래 안 나온 번호만 몰리지 않도록 상한을 두고 장기·최근 중립성으로 보정합니다.",
        {"overdue_capped": 0.48, "gap_surprise": 0.22, "long_neutral": 0.18, "recent_neutral": 0.12},
        pair_weight=0.07,
        balance_weight=0.10,
        diversity_weight=0.08,
    ),
    MethodDefinition(
        METHOD_PAIR_COOCCURRENCE,
        "공개 공식 · 동반출현쌍",
        "공개 분석식",
        "전체 회차와 최근 120회에서 두 번호가 함께 나온 횟수를 무작위 기대값과 비교해 강한 연결을 찾습니다. 단일 번호 빈도보다 번호 사이의 관계를 더 크게 봅니다.",
        {"graph_strength": 0.52, "frequency_100": 0.18, "transition": 0.16, "gap_balance": 0.14},
        pair_weight=0.30,
        balance_weight=0.06,
    ),
    MethodDefinition(
        METHOD_TRIPLET_COOCCURRENCE,
        "공개 공식 · 삼중 동반출현",
        "공개 분석식",
        "세 번호가 같은 회차에 함께 등장한 조합을 전체 및 최근 구간에서 평가합니다. 두 번호짜리 동반출현보다 더 강한 묶음 구조를 찾되 빈도 부족으로 인한 과대평가를 막기 위해 최근성과 장기 중립성을 함께 사용합니다.",
        {"triplet_strength": 0.46, "graph_strength": 0.20, "frequency_100": 0.14, "gap_balance": 0.10, "long_neutral": 0.10},
        triplet_weight=0.28,
        pair_weight=0.08,
        balance_weight=0.06,
        pool_size=23,
    ),
    MethodDefinition(
        METHOD_RECENCY_DECAY,
        "공개 공식 · 지수감쇠 최근성",
        "공개 분석식",
        "가장 최근 회차에 큰 가중치를 주고 과거로 갈수록 반감기 방식으로 영향력을 줄입니다. 고정 10·30회 경계 대신 연속적인 최근성 가중치를 사용합니다.",
        {"frequency_decay": 0.58, "frequency_30": 0.16, "frequency_100": 0.10, "graph_strength": 0.08, "gap_balance": 0.08},
        pair_weight=0.08,
        balance_weight=0.09,
        diversity_weight=0.05,
    ),
    MethodDefinition(
        METHOD_BAYESIAN_SHRINKAGE,
        "공개 공식 · 베이지안 수축",
        "공개 분석식",
        "최근 60회 출현률을 전체 평균 6/45 쪽으로 수축시켜 작은 표본의 과도한 핫/콜드 판단을 완화합니다. 최근 빈도와 장기 중립성을 함께 사용해 극단값을 보수적으로 평가합니다.",
        {"bayesian_60": 0.52, "recent_neutral": 0.16, "long_neutral": 0.14, "graph_strength": 0.10, "gap_balance": 0.08},
        pair_weight=0.08,
        balance_weight=0.10,
        diversity_weight=0.06,
    ),
    MethodDefinition(
        METHOD_CYCLE_RHYTHM,
        "공개 공식 · 재등장 주기",
        "공개 분석식",
        "각 번호의 과거 등장 간격 분포에서 중앙 재등장 주기를 구하고 현재 미출현 간격이 그 주기에 얼마나 가까운지 평가합니다. 로또가 기억을 가진다는 의미는 아니며 주기형 휴리스틱으로만 사용합니다.",
        {"cycle_fit": 0.46, "gap_balance": 0.18, "frequency_100": 0.14, "transition": 0.12, "long_neutral": 0.10},
        pair_weight=0.08,
        balance_weight=0.10,
        diversity_weight=0.08,
    ),
    MethodDefinition(
        METHOD_BALANCE,
        "공개 공식 · 균형 필터",
        "공개 분석식",
        "번호합, 홀짝, 1~22/23~45 비율, 번호대 분산, 전체 범위를 과거 조합의 전형적인 중심 구간에 가깝게 맞춥니다. 개별 번호보다 조합의 형태를 우선합니다.",
        {"long_neutral": 0.32, "recent_neutral": 0.28, "gap_balance": 0.22, "frequency_100": 0.18},
        pair_weight=0.05,
        balance_weight=0.36,
        diversity_weight=0.10,
        pool_size=24,
    ),
    MethodDefinition(
        METHOD_DELTA,
        "공개 공식 · 델타 시스템",
        "공개 분석식",
        "오름차순 번호 사이의 차이값(델타), 중복 델타, 최대 간격, 전체 범위를 평가하는 전통적인 델타 필터입니다. 지나치게 몰리거나 지나치게 벌어진 조합을 피하는 데 사용합니다.",
        {"long_neutral": 0.30, "recent_neutral": 0.24, "gap_balance": 0.20, "frequency_100": 0.16, "graph_strength": 0.10},
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
        "직전 회차 번호가 다음 회차에 일부 다시 등장하는 이월수 관찰을 활용합니다. 1~2개 이월을 가장 높게 평가하고 전이·최근 빈도·번호쌍을 함께 봅니다.",
        {"transition": 0.34, "frequency_30": 0.23, "gap_balance": 0.18, "graph_strength": 0.15, "long_neutral": 0.10},
        pair_weight=0.10,
        balance_weight=0.08,
        carryover_weight=0.34,
        diversity_weight=0.05,
    ),
    MethodDefinition(
        METHOD_PUBLIC_ENSEMBLE,
        "공개 공식 · 종합 앙상블",
        "추천 공개 분석식",
        "가중 빈도·최근성·미출현·동반출현·균형·델타·이월수 등 성격이 다른 공개형 휴리스틱을 합의 점수로 결합한 권장안입니다. 한 가지 공식의 우연한 과적합을 줄이는 것이 목적입니다.",
        {"frequency_10": 0.08, "frequency_30": 0.10, "frequency_100": 0.10, "frequency_decay": 0.08, "bayesian_60": 0.08, "overdue_capped": 0.08, "transition": 0.10, "graph_strength": 0.12, "triplet_strength": 0.08, "long_neutral": 0.04, "gap_balance": 0.04},
        pair_weight=0.14,
        triplet_weight=0.07,
        balance_weight=0.15,
        delta_weight=0.11,
        carryover_weight=0.09,
        diversity_weight=0.10,
        pool_size=24,
    ),
    MethodDefinition(
        METHOD_MYUNGRI_HETU,
        "명리 권장 · 일진 오행·하도 수리",
        "전통 명리 권장",
        "다음 추첨일의 60갑자 일주 천간(日干/Day Master)·지지 오행과 하도(河圖) 수리오행을 결합합니다. 전통 체계의 계산 규칙은 재현 가능하지만 로또 당첨 확률 상승이 과학적으로 검증된 방식은 아닙니다.",
        {"myungri_resonance": 0.60, "graph_strength": 0.12, "transition": 0.10, "gap_balance": 0.08, "frequency_100": 0.05, "long_neutral": 0.05},
        pair_weight=0.08,
        balance_weight=0.10,
        diversity_weight=0.06,
        myungri_weight=0.34,
        pool_size=20,
    ),
)

METHODS_BY_ID: Final = {method.method_id: method for method in METHODS}

DEFAULT_METHOD_IDS: Final[tuple[str, ...]] = (
    METHOD_PHASE_RESIDUAL,
    METHOD_TRANSITION_GAP,
    METHOD_WEIGHTED_FREQUENCY,
    METHOD_PAIR_COOCCURRENCE,
    METHOD_PUBLIC_ENSEMBLE,
    METHOD_MYUNGRI_HETU,
)

PUBLIC_METHOD_IDS: Final[tuple[str, ...]] = tuple(
    method.method_id for method in METHODS if method.category in {"공개 분석식", "추천 공개 분석식"}
)
TRADITIONAL_METHOD_IDS: Final[tuple[str, ...]] = tuple(
    method.method_id for method in METHODS if method.category == "전통 명리 권장"
)


def normalize_method_ids(value: object) -> tuple[str, ...]:
    """Validate, deduplicate, and preserve configured method order."""
    if not isinstance(value, (list, tuple)):
        return DEFAULT_METHOD_IDS
    result: list[str] = []
    for item in value:
        method_id = str(item)
        if method_id in METHODS_BY_ID and method_id not in result:
            result.append(method_id)
    return tuple(result) or DEFAULT_METHOD_IDS


def method_selector_options() -> list[dict[str, str]]:
    """Return concise labels with enough context for the HA selector."""
    return [
        {"value": method.method_id, "label": f"{method.label} — {method.description}"}
        for method in METHODS
    ]


def method_catalog() -> list[dict[str, str]]:
    """Return a user-facing explanation catalog for sensor attributes/UI help."""
    return [
        {
            "method_id": method.method_id,
            "name": method.label,
            "category": method.category,
            "description": method.description,
        }
        for method in METHODS
    ]
