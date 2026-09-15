"""Research-backed objectives, not winning-number prediction.

Crowd avoidance is an UNFITTED preference heuristic: purchased-ticket data is
not available. Triple coverage is a portfolio surrogate, not full-draw coverage.
The four-ticket wheel has an exact conditional covering guarantee.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
from itertools import combinations
from math import comb, exp, fsum, lgamma, log
from secrets import SystemRandom

CROWD_ID = "crowd_pattern_avoidance"
COVERAGE_ID = "portfolio_triplet_coverage"
RESEARCH_IDS = (CROWD_ID, COVERAGE_ID)
CANDIDATE_LIMIT = 256
TOTAL_COMBINATIONS = comb(45, 6)


def _ticket(values: Iterable[int]) -> tuple[int, ...]:
    numbers = tuple(values)
    if (len(numbers) != 6 or len(set(numbers)) != 6
            or any(type(n) is not int or not 1 <= n <= 45 for n in numbers)):
        raise ValueError("번호는 1~45의 중복 없는 정수 6개여야 합니다")
    return tuple(sorted(numbers))


def preference_features(values: Iterable[int]) -> dict[str, int]:
    """Explicit, uncalibrated features; short adjacent pairs are NOT excluded."""
    ticket = _ticket(values)
    longest = run = 1
    for a, b in zip(ticket, ticket[1:]):
        run = run + 1 if b == a + 1 else 1
        longest = max(longest, run)
    return {
        "all_within_31": int(ticket[-1] <= 31),
        "four_or_more_consecutive": int(longest >= 4),
        "six_number_arithmetic_sequence": int(len({b - a for a, b in zip(ticket, ticket[1:])}) == 1),
        "four_or_more_same_last_digit": int(max(Counter(n % 10 for n in ticket).values()) >= 4),
    }


def preference_penalty(values: Iterable[int]) -> int:
    features = preference_features(values)
    # Fixed design choices, NOT estimated probabilities or empirically fitted weights.
    return sum(features.values())


def coverage_details(values: Iterable[int], references: Sequence[Sequence[int]]) -> dict:
    ticket = _ticket(values)
    refs = tuple(dict.fromkeys(_ticket(row) for row in references))
    covered = {group for row in refs for group in combinations(row, 3)}
    groups = set(combinations(ticket, 3))
    return {
        "reference_ticket_count": len(refs),
        "covered_triplets_before": len(covered),
        "new_triplets": len(groups - covered),
        "covered_triplets_after": len(covered | groups),
        "total_possible_triplets": comb(45, 3),
        "maximum_reference_overlap": max((len(set(ticket) & set(row)) for row in refs), default=0),
        "coverage_metric": "unique_three_number_subsets_not_winning_probability",
    }


def select_ticket(formula_id: str, fixed: tuple[int, ...], blocked: set[tuple[int, ...]],
                  rng, references: Sequence[Sequence[int]] = ()) -> tuple[int, ...]:
    """Bounded candidate search, strict exclusions, randomized ties.

    Small remaining spaces are searched exactly. Large spaces use at most 256
    allowed proposals. There is no global optimality or uniformity claim.
    """
    from .sampling import generate_ticket, rank_subset, unrank

    if formula_id not in RESEARCH_IDS:
        raise ValueError("Unknown research formula")
    refs = tuple(dict.fromkeys(_ticket(row) for row in references))
    if formula_id == COVERAGE_ID and not refs:
        return generate_ticket("uniform_fisher_yates", fixed, excluded_combinations=blocked, rng=rng)
    pool = tuple(n for n in range(1, 46) if n not in fixed)
    k = 6 - len(fixed)
    if comb(len(pool), k) <= CANDIDATE_LIMIT:
        candidates = [tuple(sorted((*fixed, *extra))) for extra in combinations(pool, k)]
        candidates = [row for row in candidates if row not in blocked]
    else:
        # Validate exclusions once in sampling.generate_ticket, then map allowed
        # ranks exactly. Do not revalidate 1,000+ historical rows per proposal.
        forbidden = sorted(rank_subset(pool, tuple(n for n in row if n not in fixed))
                           for row in blocked)
        total = comb(len(pool), k) - len(forbidden)
        proposals = []
        for _ in range(CANDIDATE_LIMIT):
            rank = rng.randrange(total)
            for excluded in forbidden:
                if excluded > rank:
                    break
                rank += 1
            proposals.append(tuple(sorted((*fixed, *unrank(pool, k, rank)))))
        candidates = list(dict.fromkeys(proposals))
    if not candidates:
        raise ValueError("고정번호와 제외 조건을 만족하는 새 조합이 없습니다")
    triples = {group for row in refs for group in combinations(row, 3)}
    usage = Counter(n for row in refs for n in row)
    ref_sets = tuple(set(row) for row in refs)

    def objective(ticket):
        if formula_id == CROWD_ID:
            return (-preference_penalty(ticket),)
        return (sum(group not in triples for group in combinations(ticket, 3)),
                -max((len(set(ticket) & row) for row in ref_sets), default=0),
                -sum(usage[n] for n in ticket))

    scored = [(objective(row), row) for row in candidates]
    best = max(score for score, _ in scored)
    tied = [row for score, row in scored if score == best]
    return tied[rng.randrange(len(tied))]


def recommendation_details(formula_id: str, ticket: Sequence[int],
                           references: Sequence[Sequence[int]] = ()) -> dict:
    common = {
        "uniformity": "nonuniform_selection_heuristic",
        "predictive_evidence": "not_established",
        "history_used_for_weighting": False,
        "candidate_limit": CANDIDATE_LIMIT,
        "global_optimality_proven": False,
        "score_meaning": "선택 기준을 설명하는 지표이며 당첨확률 또는 적중률이 아닙니다",
        "validation_scope": "번호·제외 조건과 조합 지표 검증; 예측력 및 기대수익 개선 미검증",
    }
    if formula_id == CROWD_ID:
        common.update({
            "objective": "avoid_explicit_purchase_pattern_proxies",
            "preference_features": preference_features(ticket),
            "preference_penalty": preference_penalty(ticket),
            "purchase_data_available": False,
            "maximum_entropy_fitted": False,
            "expected_return_improvement": None,
            "research_notice": "구매 데이터 없는 비인기 패턴 회피 휴리스틱입니다. 최대엔트로피 학습 결과나 실제 인기 확률이 아닙니다.",
        })
    elif formula_id == COVERAGE_ID:
        common.update(coverage_details(ticket, references))
        common.update({
            "objective": "maximize_new_triplets_then_reduce_overlap",
            "fallback": "uniform_no_reference" if not references else None,
            "research_notice": "다른 로컬 추천과 중복되지 않는 3수 부분집합을 우선합니다. 전체 추첨 결과의 당첨 범위를 직접 최적화한 값은 아닙니다.",
        })
        if not references:
            common["uniformity"] = "uniform_over_allowed_combinations"
    else:
        raise ValueError("Unknown research formula")
    return common


def _pairings(numbers: tuple[int, ...]):
    if not numbers:
        yield ()
        return
    first = numbers[0]
    for index in range(1, len(numbers)):
        rest = numbers[1:index] + numbers[index + 1:]
        for tail in _pairings(rest):
            yield ((first, numbers[index]), *tail)


def covering_wheel(candidates: Iterable[int], *, excluded_combinations=(), rng=None) -> dict:
    """C(8,6,3) construction. All four games or explicit failure, never partial."""
    numbers = tuple(candidates)
    if (len(numbers) != 8 or len(set(numbers)) != 8
            or any(type(n) is not int or not 1 <= n <= 45 for n in numbers)):
        raise ValueError("후보번호는 1~45의 중복 없는 정수 8개여야 합니다")
    numbers = tuple(sorted(numbers))
    blocked = {_ticket(row) for row in excluded_combinations}
    allowed = []
    for pairs in _pairings(numbers):
        tickets = tuple(tuple(n for n in numbers if n not in pair) for pair in pairs)
        if not any(ticket in blocked for ticket in tickets):
            allowed.append(tickets)
    if not allowed:
        raise ValueError("제외 조건을 지키는 4게임 휠링이 없습니다. 후보번호를 바꾸세요")
    rng = rng if rng is not None else SystemRandom()
    tickets = allowed[rng.randrange(len(allowed))]
    return {
        "formula_id": "covering_8_6_3", "formula_version": 1,
        "candidate_numbers": list(numbers), "tickets": [list(row) for row in tickets],
        "ticket_count": 4, "covered_triplets": 56, "candidate_triplets": comb(8, 3),
        "conditional_minimum_matches": {"3": 3, "4": 3, "5": 4, "6": 5},
        "first_prize_probability_all_four": 4 / TOTAL_COMBINATIONS,
        "first_prize_odds_per_ticket": "1/8,145,060",
        "notice": "4게임 전체에만 조건부 보장이 적용됩니다. 후보 8개 안에 본번호가 3·4·5·6개 있으면 한 게임 이상이 각각 3·3·4·5개 일치합니다. 후보 적중이나 1등을 보장하지 않습니다.",
        "saved_as_purchase": False,
    }


def fairness_diagnostic(history: Sequence[Sequence[int]]) -> dict:
    """Finite-population corrected Pearson statistic, df=44.

    Chi-square survival uses its exact finite-sum expression for even df.
    The REFERENCE distribution itself is asymptotic, not an exact finite-N test.
    This checks marginal counts only, not serial independence or every bias.
    """
    rows = [_ticket(row) for row in history]
    if not rows:
        return {"status": "insufficient_history", "sample_size": 0, "p_value": None}
    counts = Counter(n for row in rows for n in row)
    expected = len(rows) * 6 / 45
    raw = fsum((counts[n] - expected) ** 2 / expected for n in range(1, 46))
    statistic = raw * 44 / 39
    x = statistic / 2
    if x == 0:
        p_value = 1.0
    else:
        terms = [-x + k * log(x) - lgamma(k + 1) for k in range(22)]
        largest = max(terms)
        p_value = min(1.0, exp(largest) * fsum(exp(t - largest) for t in terms))
    sufficient = expected >= 5
    return {
        "status": "asymptotic_reference" if sufficient else "insufficient_expected_count",
        "sample_size": len(rows), "expected_count_per_number": expected,
        "counts": {str(n): counts[n] for n in range(1, 46)},
        "raw_pearson_statistic": raw, "finite_population_correction": 44 / 39,
        "corrected_statistic": statistic, "degrees_of_freedom": 44,
        "p_value": p_value if sufficient else None,
        "reference_distribution": "asymptotic_chi_square_not_exact",
        "used_for_recommendations": False,
        "notice": "개별 번호의 출현 빈도만 진단합니다. p값은 당첨확률이 아니며, 작은 p값도 조작 또는 예측 가능성을 확정하지 않습니다. 기대횟수 5 미만에서는 p값을 표시하지 않습니다.",
    }
