"""Install research-backed selection objectives without rewriting legacy formulas."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from secrets import SystemRandom

from .research_formulas import (
    COVERAGE_ID,
    CROWD_ID,
    RESEARCH_IDS,
    fairness_diagnostic,
    recommendation_details,
    select_ticket,
)

_INSTALLED = False


def install_research_extensions() -> None:
    """Extend catalog/sampling before coordinator imports analysis.

    The patch is additive: saved method IDs, default selection and every legacy
    sampler remain unchanged. Research objectives are explicitly non-predictive.
    """
    global _INSTALLED
    if _INSTALLED:
        return

    from . import methods, sampling

    crowd = methods.MethodDefinition(
        CROWD_ID,
        "분할 위험 참고 · 비인기 패턴 회피",
        "구매 성향 휴리스틱",
        (
            "생일 범위·긴 연속수·6수 등차수열·동일 끝자리 집중 같은 구매 선호 대리지표를 "
            "피하는 후보를 탐색합니다. 실제 구매 데이터로 적합한 최대엔트로피 모형이 아니며 "
            "당첨확률 또는 기대상금 증가를 보장하지 않습니다."
        ),
        {}, pool_size=45, sampling=CROWD_ID, formula_version=1,
    )
    coverage = methods.MethodDefinition(
        COVERAGE_ID,
        "조합 설계 · 3수 커버리지 보완",
        "여러 게임 조합 설계",
        (
            "같은 생성 배치에서 앞서 선택된 로컬 추천과 겹치지 않는 3수 부분집합이 많은 후보를 "
            "우선합니다. 최대 256개 허용 후보를 비교하는 휴리스틱이며 전체 추첨 결과의 당첨 범위나 "
            "1등 확률을 높인다는 뜻은 아닙니다. 참조 추천이 없으면 균등 추출합니다."
        ),
        {}, pool_size=45, sampling=COVERAGE_ID, formula_version=1,
    )

    # Keep selected-median last in the selector while build_analysis already
    # executes it last regardless of catalog position.
    catalog = list(methods.METHODS)
    median_index = next(
        (i for i, item in enumerate(catalog) if item.method_id == methods.METHOD_SELECTED_MEDIAN),
        len(catalog),
    )
    catalog[median_index:median_index] = [crowd, coverage]
    methods.METHODS = tuple(catalog)
    methods.METHODS_BY_ID = {item.method_id: item for item in methods.METHODS}
    methods.BASIC_METHOD_IDS = tuple(
        key for key in methods.METHODS_BY_ID if key not in methods.ADVANCED_METHOD_IDS
    )
    methods.FORMULAS = methods.METHODS
    methods.FORMULAS_BY_ID = methods.METHODS_BY_ID
    methods.METHOD_CROWD_AVOIDANCE = CROWD_ID
    methods.METHOD_PORTFOLIO_COVERAGE = COVERAGE_ID

    original_generate = sampling.generate_ticket
    original_validate = sampling.validate_sampled_ticket

    def validate_sampled_ticket(formula_id: str, values: Iterable[int]) -> tuple[int, ...]:
        if formula_id not in RESEARCH_IDS:
            return original_validate(formula_id, values)
        ticket = sampling.validate_fixed(values)
        if len(ticket) != 6:
            raise ValueError("추첨 공식의 결과는 번호 6개여야 합니다")
        return ticket

    def generate_ticket(
        formula_id: str,
        fixed_numbers: Iterable[int] = (),
        *,
        excluded_combinations: Iterable[Sequence[int]] = (),
        history: Sequence[Sequence[int]] = (),
        rng=None,
    ) -> tuple[int, ...]:
        if formula_id not in RESEARCH_IDS:
            return original_generate(
                formula_id,
                fixed_numbers,
                excluded_combinations=excluded_combinations,
                history=history,
                rng=rng,
            )
        fixed = sampling.validate_fixed(fixed_numbers)
        fixed_set = set(fixed)
        blocked: set[tuple[int, ...]] = set()
        for values in excluded_combinations:
            ticket = sampling.validate_fixed(values)
            if len(ticket) != 6:
                raise ValueError("Exclusion must contain six numbers")
            if fixed_set.issubset(ticket):
                blocked.add(ticket)
        past = set()
        for row in history:
            ticket = sampling.validate_fixed(row)
            if len(ticket) != 6:
                raise ValueError("Invalid history draw")
            past.add(ticket)
        references = tuple(sorted(blocked - past)) if formula_id == COVERAGE_ID else ()
        return select_ticket(
            formula_id,
            fixed,
            blocked,
            rng if rng is not None else SystemRandom(),
            references,
        )

    sampling.generate_ticket = generate_ticket
    sampling.validate_sampled_ticket = validate_sampled_ticket

    # Import only after sampling/catalog are extended so every later direct
    # import (coordinator, validation, cache) receives the research-aware hooks.
    from . import analysis

    original_build = analysis.build_analysis

    def build_analysis(*args, **kwargs):
        result = original_build(*args, **kwargs)
        prior_tickets: list[tuple[int, ...]] = []
        for rec in result.recommendations:
            if rec.method_id in RESEARCH_IDS:
                references = prior_tickets if rec.method_id == COVERAGE_ID else ()
                rec.details.update(recommendation_details(rec.method_id, rec.numbers, references))
                rec.details["eligible_combination_count"] = None
                rec.details["research_formula"] = True
            prior_tickets.append(tuple(rec.numbers))
        history = args[0] if args else kwargs.get("history", ())
        result.summary["fairness_diagnostic"] = fairness_diagnostic(
            [tuple(draw.numbers) for draw in history]
        )
        result.summary["research_formula_ids"] = list(RESEARCH_IDS)
        return result

    analysis.build_analysis = build_analysis
    _INSTALLED = True
