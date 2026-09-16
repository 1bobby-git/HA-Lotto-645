"""Single-ticket, unfitted purchase-pattern preference; not prediction."""
from collections import Counter
from collections.abc import Iterable, Sequence
from itertools import combinations
from math import comb
CANDIDATE_LIMIT = 256

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

def select_ticket(fixed: tuple[int, ...], blocked: set[tuple[int, ...]], rng) -> tuple[int, ...]:
    """Bounded candidate search, strict exclusions, randomized ties.

    Small remaining spaces are searched exactly. Large spaces use at most 256
    allowed proposals. There is no global optimality or uniformity claim.
    """
    from .sampling import generate_ticket, rank_subset, unrank

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
    def objective(ticket):
        return (-preference_penalty(ticket),)

    scored = [(objective(row), row) for row in candidates]
    best = max(score for score, _ in scored)
    tied = [row for score, row in scored if score == best]
    return tied[rng.randrange(len(tied))]

def recommendation_details(ticket: Sequence[int]) -> dict:
    common = {
        "uniformity": "nonuniform_selection_heuristic",
        "predictive_evidence": "not_established",
        "history_used_for_weighting": False,
        "candidate_limit": CANDIDATE_LIMIT,
        "global_optimality_proven": False,
        "score_meaning": "선택 기준을 설명하는 지표이며 당첨확률 또는 적중률이 아닙니다",
        "validation_scope": "번호·제외 조건과 조합 지표 검증; 예측력 및 기대수익 개선 미검증",
    }
    common.update({
        "objective": "avoid_explicit_purchase_pattern_proxies",
        "preference_features": preference_features(ticket),
        "preference_penalty": preference_penalty(ticket),
        "purchase_data_available": False,
        "maximum_entropy_fitted": False,
        "expected_return_improvement": None,
        "research_notice": "구매 데이터 없는 비인기 패턴 회피 휴리스틱입니다. 최대엔트로피 학습 결과나 실제 인기 확률이 아닙니다.",
    })

    return common
