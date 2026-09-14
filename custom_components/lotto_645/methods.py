"""Selectable recommendation method catalog for Lotto 6/45.

Uniform formulas use OS CSPRNG sampling. Legacy profiles are experimental
ranking/filtering heuristics. No formula improves an individual ticket's odds.
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
    sampling: str | None = None
    formula_version: int = 1


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
METHOD_SELECTED_MEDIAN: Final = "selected_median_consensus"
# Keep the legacy ID for existing config-entry compatibility.
METHOD_MYUNGRI_HETU: Final = "myungri_hetu_day_pillar"

METHOD_UNIFORM_FISHER_YATES: Final = "uniform_fisher_yates"
METHOD_UNIFORM_FLOYD: Final = "uniform_floyd"
METHOD_UNIFORM_REJECTION: Final = "uniform_rejection"
METHOD_UNIFORM_SEQUENTIAL: Final = "uniform_sequential"
METHOD_CALIBRATED_STRATIFIED: Final = "calibrated_stratified"
METHOD_UNIFORM_COMBINATION_RANK: Final = "uniform_combination_rank"

METHODS: Final[tuple[MethodDefinition, ...]] = (
    MethodDefinition(
        METHOD_UNIFORM_FISHER_YATES,
        "균등 공식 · 부분 Fisher–Yates",
        "균등 추첨 공식",
        "남은 번호 중 하나를 편향 없는 정수 난수로 선택해 교환합니다. OS CSPRNG 기반 비복원추출입니다. 기존 과거 1등 제외 조건이 켜진 생성 경로에서는 허용된 조합 안에서 균등합니다. 당첨확률은 높아지지 않습니다.",
        {}, pool_size=45, sampling="uniform_fisher_yates",
    ),
    MethodDefinition(
        METHOD_UNIFORM_FLOYD,
        "균등 공식 · Floyd",
        "균등 추첨 공식",
        "중복 사건을 아직 처리하지 않은 인덱스로 대응시켜 균등한 부분집합을 생성합니다. 기존 과거 1등 제외 조건이 켜진 생성 경로에서는 허용된 조합 안에서 균등합니다. 당첨확률은 높아지지 않습니다.",
        {}, pool_size=45, sampling="uniform_floyd",
    ),
    MethodDefinition(
        METHOD_UNIFORM_REJECTION,
        "균등 공식 · 중복거부",
        "균등 추첨 공식",
        "이미 선택한 번호가 나오면 다시 추첨합니다. 반복 상한에 도달해도 균등한 잔여 추출로 마무리합니다. 기존 과거 1등 제외 조건이 켜진 생성 경로에서는 허용된 조합 안에서 균등합니다. 당첨확률은 높아지지 않습니다.",
        {}, pool_size=45, sampling="uniform_rejection",
    ),
    MethodDefinition(
        METHOD_UNIFORM_SEQUENTIAL,
        "균등 공식 · 순차 포함",
        "균등 추첨 공식",
        "각 번호를 남은 필요 개수/남은 번호 수 확률로 포함합니다. 실수 비교 대신 정확한 정수 난수를 사용합니다. 기존 과거 1등 제외 조건이 켜진 생성 경로에서는 허용된 조합 안에서 균등합니다. 당첨확률은 높아지지 않습니다.",
        {}, pool_size=45, sampling="uniform_sequential",
    ),
    MethodDefinition(
        METHOD_CALIBRATED_STRATIFIED,
        "균등 공식 · 조합보정 층화 CCSS",
        "균등 추첨 공식",
        "구간별 배분을 조합 개수로 보정합니다. 구간 균형을 강제하지 않아 조건부 균등성을 유지합니다. 기존 과거 1등 제외 조건이 켜진 생성 경로에서는 허용된 조합 안에서 균등합니다. 당첨확률은 높아지지 않습니다.",
        {}, pool_size=45, sampling="calibrated_stratified",
    ),
    MethodDefinition(
        METHOD_UNIFORM_COMBINATION_RANK,
        "균등 공식 · 조합 인덱스",
        "균등 추첨 공식",
        "가능한 조합의 인덱스 하나를 균등하게 뽑아 번호로 변환합니다. 연구 보고서 외 추가한 조합론적 공식입니다. 기존 과거 1등 제외 조건이 켜진 생성 경로에서는 허용된 조합 안에서 균등합니다. 당첨확률은 높아지지 않습니다.",
        {}, pool_size=45, sampling="uniform_combination_rank",
    ),

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
        "최근 30·120·260회와 전체 구간의 잔차·곡률·전이를 결합합니다. 전이·그래프·간격을 보조로 사용해 한 구간의 일시적 급등에만 끌려가지 않도록 구성했습니다.",
        {"phase_velocity": 0.22, "curvature": 0.19, "counter_phase": 0.18, "transition": 0.16, "graph_strength": 0.15, "gap_balance": 0.10},
        pair_weight=0.16,
        diversity_weight=0.13,
        balance_weight=0.08,
    ),
    MethodDefinition(
        METHOD_WEIGHTED_FREQUENCY,
        "공개 공식 · 가중 빈도",
        "공개 분석식",
        "최근 10·30·100회와 전체 출현 빈도에 서로 다른 비중을 주는 공식입니다. 최근성은 반영하지만 장기 통계도 남겨 특정 짧은 구간에 과도하게 맞추지 않습니다.",
        {"frequency_10": 0.34, "frequency_30": 0.28, "frequency_100": 0.23, "frequency_long": 0.15},
        pair_weight=0.08,
        balance_weight=0.10,
        diversity_weight=0.06,
    ),
    MethodDefinition(
        METHOD_HOT_NUMBERS,
        "공개 공식 · 핫넘버",
        "공개 분석식",
        "최근 10·30회에서 출현이 늘고 있는 번호를 우선하는 전형적인 핫넘버 공식입니다. 번호대와 조합 내부 연결을 함께 보정해 최근 번호만 과도하게 몰리는 현상을 줄입니다.",
        {"frequency_10": 0.44, "frequency_30": 0.34, "phase_velocity_positive": 0.22},
        pair_weight=0.10,
        balance_weight=0.08,
        diversity_weight=0.05,
    ),
    MethodDefinition(
        METHOD_OVERDUE_GAP,
        "공개 공식 · 콜드·미출현",
        "공개 분석식",
        "현재까지 나오지 않은 회차 간격이 긴 번호를 우선하는 콜드넘버 공식입니다. 극단적으로 오래 안 나온 번호만 몰리지 않도록 상한을 두고 장기·최근 중립성으로 보정합니다.",
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
        "가장 최근 회차에 큰 가중치를 주고 과거로 갈수록 반감기 공식으로 영향력을 줄입니다. 고정 10·30회 경계 대신 연속적인 최근성 가중치를 사용합니다.",
        {"frequency_decay": 0.58, "frequency_30": 0.16, "frequency_100": 0.10, "graph_strength": 0.08, "gap_balance": 0.08},
        pair_weight=0.08,
        balance_weight=0.09,
        diversity_weight=0.05,
    ),
    MethodDefinition(
        METHOD_BAYESIAN_SHRINKAGE,
        "실험 공식 · 베이지안 수축",
        "공개 분석식",
        "최근 최대 300회 빈도를 균등 사전분포(강도 500)로 수축하고 5%만 반영합니다. 순위 재확대 없이 가중 비복원추출하며 당첨 예측 근거는 없습니다.",
        {}, pool_size=45, sampling="bayesian_shrinkage", formula_version=2,
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
        "번호합 기대값 138, 홀짝·저고 중심 3개, 번호대 분산 및 범위 34를 기준으로 조합 형태를 평가합니다. 3개·34 등의 목표는 고정 휴리스틱이며 과거에서 학습한 최적값이 아닙니다. 개별 번호보다 조합의 형태를 우선합니다.",
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
        "직전 회차 번호가 다음 회차에 일부 다시 등장하는 이월수 관찰을 활용합니다. 6/45 초기하분포(하이퍼지오메트릭)의 이월 개수별 비중을 적용하고 전이·최근 빈도·번호쌍을 함께 봅니다.",
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
        "가중 빈도·최근성·미출현·동반출현·균형·델타·이월수 등 성격이 다른 공개형 휴리스틱을 합의 점수로 결합한 권장안입니다. 단일 지표 의존을 줄이는 설계이며 실제 예측력 향상이 입증된 것은 아닙니다.",
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
        "명리 권장 · 개인 사주 원국·대운·추첨일",
        "개인 사주 명리 권장",
        (
            "사용자가 입력한 생년월일·출생시간·양/음력·성별·출생지/시간대로 사주 원국의 "
            "연주·월주·일주·시주(시간 미상 시 제외), 월령·통근·투간, 십신 10종, 지장간 비율, 격국 후보를 계산합니다. "
            "억부·조후·통관·병약의 보완오행 후보와 대운·세운·월운·일시운의 합충형파해를 점수에 반영합니다. "
            "하도 끝자리 배속과 점수 가중치는 현대 응용이며 용신 확정·당첨 예측이 아닙니다. 각 번호의 십신과 점수 근거를 공개합니다. "
            "개인 사주정보 입력 전에는 이 공식이 활성화되지 않습니다."
        ),
        {"myungri_resonance": 0.72, "graph_strength": 0.08, "transition": 0.07, "gap_balance": 0.05, "frequency_100": 0.04, "long_neutral": 0.04},
        pair_weight=0.05,
        balance_weight=0.06,
        diversity_weight=0.05,
        myungri_weight=0.52,
        pool_size=22,
    ),
    MethodDefinition(
        METHOD_SELECTED_MEDIAN,
        "합의 추천 · 선택 공식 중앙값",
        "선택 공식 집계",
        (
            "현재 함께 선택한 다른 로컬 추첨 공식들의 1~45 번호별 0~1 적합도를 모아 각 번호의 중앙값을 계산합니다. "
            "한 공식의 극단값이 전체를 끌고 가지 않도록 중앙값을 사용하며, 그 중앙값이 높은 번호들로 최종 6개 조합을 만듭니다. "
            "AI 추천은 집계에서 제외하고, 명리 공식은 사용자가 함께 선택한 경우에만 포함합니다. 의미 있는 중앙값을 위해 다른 추첨 공식 2개 이상이 필요합니다."
        ),
        {},
        pool_size=26,
    ),
)

METHODS_BY_ID: Final = {method.method_id: method for method in METHODS}

# Personal Saju is intentionally not selected by default. A user must explicitly
# select it and complete the birth-profile step before the integration may use it.
DEFAULT_METHOD_IDS: Final[tuple[str, ...]] = (
    METHOD_UNIFORM_FISHER_YATES,
    METHOD_UNIFORM_FLOYD,
    METHOD_UNIFORM_REJECTION,
    METHOD_UNIFORM_SEQUENTIAL,
    METHOD_CALIBRATED_STRATIFIED,
)

PUBLIC_METHOD_IDS: Final[tuple[str, ...]] = tuple(
    method.method_id for method in METHODS if method.category in {"공개 분석식", "추천 공개 분석식"}
)
TRADITIONAL_METHOD_IDS: Final[tuple[str, ...]] = (METHOD_MYUNGRI_HETU,)


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
        {
            "value": method.method_id,
            "label": (
                f"{method.label} [사주정보 입력 필요] — {method.description}"
                if method.method_id == METHOD_MYUNGRI_HETU
                else f"{method.label} — {method.description}"
            ),
        }
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
            "requirements": (
                "생년월일, 출생시간, 양력/음력, 성별, 출생지, 시간대"
                if method.method_id == METHOD_MYUNGRI_HETU
                else "다른 점수형 추첨 공식 2개 이상 (균등 샘플링 제외)"
                if method.method_id == METHOD_SELECTED_MEDIAN
                else "없음"
            ),
        }
        for method in METHODS
    ]


# Additive semantic aliases; saved IDs and automation keys stay compatible.
FormulaDefinition = MethodDefinition
FORMULAS = METHODS
FORMULAS_BY_ID = METHODS_BY_ID
DEFAULT_FORMULA_IDS = DEFAULT_METHOD_IDS
normalize_formula_ids = normalize_method_ids


def resolve_formula(data: dict, default: str) -> str:
    """Prefer the semantic key without breaking legacy automation payloads."""
    return data.get("formula_id", data.get("formula", data.get("method_id", data.get("method", default))))


def is_score_formula(method_id: str) -> bool:
    return method_id != METHOD_SELECTED_MEDIAN and (method_id == METHOD_BAYESIAN_SHRINKAGE or not METHODS_BY_ID[method_id].sampling)
