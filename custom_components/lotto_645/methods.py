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
METHOD_AC_FILTER: Final = "ac_range_filter"
METHOD_CONSTRAINT_UNIFORM: Final = "constraint_uniform"
METHOD_PERSONAL_LUCKY: Final = "personal_lucky"
METHOD_SELECTED_VOTE: Final = "selected_vote_consensus"

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
        "빈도 프리셋 · 핫넘버",
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
        METHOD_RECENCY_DECAY,
        "빈도 프리셋 · 지수감쇠 최근성",
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
        "복합 공식 · 공개 지표 종합",
        "공개 분석식",
        "가중 빈도·최근성·미출현·동반출현·균형·델타·이월수 등 성격이 다른 공개형 휴리스틱을 복합 선호 점수로 결합합니다. 단일 지표 의존을 줄이는 설계이며 실제 예측력 향상이 입증된 것은 아닙니다.",
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
        METHOD_AC_FILTER,
        "형태 공식 · AC값 7 이상",
        "조합 형태 필터",
        "15개 번호쌍의 서로 다른 양의 차이 개수에서 5를 뺀 AC값이 7 이상인 조합을 조건부 균등 추출합니다. 인접 간격을 평가하는 델타와 다르며 빈도·합계·홀짝 점수를 섞지 않습니다. 전체 조합의 약 85.24%가 해당하고, 이 비율은 적중률이 아닙니다. 당첨확률은 높아지지 않습니다.",
        {}, pool_size=45, sampling="ac_range_filter",
    ),
    MethodDefinition(
        METHOD_CONSTRAINT_UNIFORM,
        "조건 공식 · 조건 지정 균등 생성",
        "조합 조건 생성",
        "고정·제외번호, 합계·홀짝·저고·끝수·연속수·AC·이월수·이웃수·소수·3배수 조건 안에서 균등 추출합니다. 조건 충돌과 탐색 한도를 구분하며 임의 완화하지 않습니다. 통합 설정의 조건 지정 생성에서 조건을 저장하세요.",
        {}, pool_size=45, sampling="constraint_uniform",
    ),
    MethodDefinition(
        METHOD_PERSONAL_LUCKY,
        "재미 공식 · 개인 행운 번호",
        "재미·개인화",
        "별명·소원·꿈 키워드를 로컬 SHA-256 규칙과 새 난수로 변환합니다. 생년월일이 필요 없으며 새로고침마다 다시 생성합니다. 입력은 AI나 로또 미러로 전송하지 않습니다. 꿈해몽·당첨 예측이 아닌 재미용입니다.",
        {}, pool_size=45, sampling="personal_lucky",
    ),
    MethodDefinition(
        METHOD_SELECTED_MEDIAN,
        "합의 추천 · 선택 공식 중앙값",
        "선택 공식 집계",
        (
            "선택한 다른 로컬 공식의 실제 추천번호 6개를 정렬하고 같은 순번끼리 중앙값을 계산해 ±1 범위에서 구성합니다. "
            "원본 추천번호 변경·공식 추가·제거 시 자동 갱신하며 같은 입력에서는 번호를 유지합니다. "
            "균등·실험 공식도 포함하고 AI와 자기 자신은 제외합니다. 다른 공식 2개 이상이 필요합니다."
        ),
        {},
        pool_size=0,
        formula_version=2,
    ),
    MethodDefinition(
        METHOD_SELECTED_VOTE,
        "합의 추천 · 계열별 다수결",
        "선택 공식 집계",
        "선택한 다른 로컬 공식의 번호별 표를 같은 계열의 공식 수로 나누어 집계합니다. 균등 구현·빈도 프리셋의 중복 투표를 줄이며 AI·집계 공식은 제외합니다. 원본 번호 변경 시 자동 갱신하고 기존 중앙값은 변경하지 않습니다.",
        {}, pool_size=0,
    ),
)

RETIRED_METHOD_LABELS: Final = {'cycle_rhythm': '공개 공식 · 재등장 주기', 'triplet_cooccurrence': '공개 공식 · 삼중 동반출현', 'multiscale_resonance': '독창 패턴 · 다중시간대 공명', 'transition_gap_phase': '독창 패턴 · 전이·간격 위상', 'phase_residual_graph': '독창 패턴 · 위상잔차 그래프'}

METHODS_BY_ID: Final = {method.method_id: method for method in METHODS}

# Personal Saju is intentionally not selected by default. A user must explicitly
# select it and complete the birth-profile step before the integration may use it.
DEFAULT_METHOD_IDS: Final[tuple[str, ...]] = (
    METHOD_UNIFORM_FISHER_YATES,
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


# Same-distribution implementations and frequency variants belong in advanced
# settings. Saved IDs remain stable; existing selections are not silently merged.
ADVANCED_METHOD_IDS: Final = (
    METHOD_UNIFORM_FLOYD, METHOD_UNIFORM_REJECTION, METHOD_UNIFORM_SEQUENTIAL,
    METHOD_CALIBRATED_STRATIFIED, METHOD_UNIFORM_COMBINATION_RANK,
    METHOD_HOT_NUMBERS, METHOD_RECENCY_DECAY,
)
BASIC_METHOD_IDS: Final = tuple(key for key in METHODS_BY_ID if key not in ADVANCED_METHOD_IDS)


def method_selector_options(*, advanced: bool = False) -> list[dict[str, str]]:
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
        if (method.method_id in ADVANCED_METHOD_IDS) == advanced
    ]


def method_catalog() -> list[dict[str, str]]:
    """Return a user-facing explanation catalog for sensor attributes/UI help."""
    return [
        {
            "method_id": method.method_id,
            "name": method.label,
            "category": method.category,
            "selection_group": "advanced" if method.method_id in ADVANCED_METHOD_IDS else "basic",
            "description": method.description,
            "requirements": (
                "생년월일, 출생시간, 양력/음력, 성별, 출생지, 시간대"
                if method.method_id == METHOD_MYUNGRI_HETU
                else "다른 로컬 추첨 공식 2개 이상 (균등·실험 포함, AI 제외)"
                if method.method_id in (METHOD_SELECTED_MEDIAN, METHOD_SELECTED_VOTE)
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
    return method_id not in (METHOD_SELECTED_MEDIAN, METHOD_SELECTED_VOTE) and (method_id == METHOD_BAYESIAN_SHRINKAGE or not METHODS_BY_ID[method_id].sampling)


def consensus_source_ids(method_ids) -> tuple[str, ...]:
    """All explicitly selected local formulas with actual tickets can contribute."""
    return tuple(dict.fromkeys(key for key in method_ids
                               if key in METHODS_BY_ID and key not in (METHOD_SELECTED_MEDIAN, METHOD_SELECTED_VOTE)))
