"""Auditable 6/45 samplers. Random generation is not a winning prediction.

Production uses the OS CSPRNG. Tests may inject a seeded RNG. Integer draws
avoid modulo/float mapping bias. Historical exclusion is an explicit restriction
of the sample space, NOT a way to improve a ticket's winning probability.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from collections.abc import Iterable, Sequence
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from math import comb
from secrets import SystemRandom
from typing import Protocol
from .formula_settings import CUSTOM_IDS

NUMBERS = tuple(range(1, 46))
UNIFORM_IDS = (
    "uniform_fisher_yates", "uniform_floyd", "uniform_rejection",
    "uniform_sequential", "calibrated_stratified", "uniform_combination_rank",
)
BAYESIAN_ID = "bayesian_shrinkage"
AC_FILTER_ID = "ac_range_filter"
AC_MINIMUM = 7
# Exact full-space enumeration, not historical hit rate or winning probability.
AC_ALLOWED_COMBINATIONS = 6_943_080
AC_MAX_ATTEMPTS = 512
AC_EXACT_SPACE_LIMIT = 20_000
FORMULA_VERSION = 1


class RandomSource(Protocol):
    def randrange(self, stop: int) -> int:
        """Return an unbiased integer in [0, stop)."""
        ...


def validate_fixed(values: Iterable[int]) -> tuple[int, ...]:
    numbers = tuple(values)
    if (len(numbers) > 6 or any(type(n) is not int or not 1 <= n <= 45 for n in numbers)
            or len(set(numbers)) != len(numbers)):
        raise ValueError("고정번호는 1~45의 중복 없는 정수 최대 6개여야 합니다")
    return tuple(sorted(numbers))


def ac_value(values: Iterable[int]) -> int:
    """Distinct positive differences of ALL 15 pairs, minus 5; range 0..10."""
    ticket = validate_fixed(values)
    if len(ticket) != 6:
        raise ValueError("AC값은 중복 없는 번호 6개로 계산합니다")
    return len({right - left for left, right in combinations(ticket, 2)}) - 5


def validate_sampled_ticket(formula_id: str, values: Iterable[int]) -> tuple[int, ...]:
    """Validate generated AND restored tickets against the formula contract."""
    if formula_id not in SAMPLERS and formula_id not in (BAYESIAN_ID, AC_FILTER_ID, "crowd_pattern_avoidance", *CUSTOM_IDS):
        raise ValueError("Unknown sampling formula")
    ticket = validate_fixed(values)
    if len(ticket) != 6:
        raise ValueError("추첨 공식의 결과는 번호 6개여야 합니다")
    if formula_id == AC_FILTER_ID and ac_value(ticket) < AC_MINIMUM:
        raise ValueError("저장 또는 생성된 번호가 AC 7 이상 조건을 만족하지 않습니다")
    return ticket


def fisher_yates(pool: Sequence[int], k: int, rng: RandomSource) -> tuple[int, ...]:
    values = list(pool)
    for i in range(k):
        j = i + rng.randrange(len(values) - i)
        values[i], values[j] = values[j], values[i]
    return tuple(sorted(values[:k]))


def floyd(pool: Sequence[int], k: int, rng: RandomSource) -> tuple[int, ...]:
    chosen: set[int] = set()
    for j in range(len(pool) - k, len(pool)):
        t = rng.randrange(j + 1)
        chosen.add(j if t in chosen else t)
    return tuple(sorted(pool[i] for i in chosen))


def rejection(pool: Sequence[int], k: int, rng: RandomSource) -> tuple[int, ...]:
    chosen: set[int] = set()
    for _ in range(256):
        if len(chosen) == k:
            return tuple(sorted(chosen))
        chosen.add(pool[rng.randrange(len(pool))])
    # A bounded, symmetric completion preserves uniformity; no deterministic fill.
    remaining = tuple(n for n in pool if n not in chosen)
    return tuple(sorted((*chosen, *fisher_yates(remaining, k - len(chosen), rng))))


def sequential(pool: Sequence[int], k: int, rng: RandomSource) -> tuple[int, ...]:
    chosen = []
    for i, number in enumerate(pool):
        if k == 0:
            break
        if rng.randrange(len(pool) - i) < k:
            chosen.append(number)
            k -= 1
    return tuple(sorted(chosen))


def unrank(pool: Sequence[int], k: int, rank: int) -> tuple[int, ...]:
    """Lexicographic bijection from [0, C(n,k)) to k-subsets."""
    if not 0 <= k <= len(pool) or not 0 <= rank < comb(len(pool), k):
        raise ValueError("Invalid combination rank")
    chosen = []
    for i, number in enumerate(pool):
        if not k:
            break
        block = comb(len(pool) - i - 1, k - 1)
        if rank < block:
            chosen.append(number)
            k -= 1
        else:
            rank -= block
    return tuple(chosen)


def rank_subset(pool: Sequence[int], subset: Sequence[int]) -> int:
    wanted = set(subset)
    if len(wanted) != len(subset) or not wanted.issubset(pool):
        raise ValueError("Invalid subset")
    rank, k = 0, len(wanted)
    for i, number in enumerate(pool):
        if not k:
            break
        if number in wanted:
            k -= 1
        else:
            rank += comb(len(pool) - i - 1, k - 1)
    return rank


@lru_cache(maxsize=256)
def allocation_table(capacities: tuple[int, ...], k: int):
    """Integer cumulative counts of every feasible CCSS stratum."""
    allocations, cumulative = [], []
    total = 0

    def walk(index, left, prefix, weight):
        nonlocal total
        if index == len(capacities):
            if left == 0:
                total += weight
                allocations.append(prefix)
                cumulative.append(total)
            return
        for count in range(min(capacities[index], left) + 1):
            walk(index + 1, left - count, (*prefix, count),
                 weight * comb(capacities[index], count))

    walk(0, k, (), 1)
    if total != comb(sum(capacities), k):
        raise ValueError("Invalid CCSS partition")
    return tuple(allocations), tuple(cumulative)


def stratified(pool: Sequence[int], k: int, rng: RandomSource) -> tuple[int, ...]:
    buckets = tuple(tuple(n for n in pool if (n - 1) // 10 == j) for j in range(5))
    allocations, cdf = allocation_table(tuple(map(len, buckets)), k)
    allocation = allocations[bisect_right(cdf, rng.randrange(cdf[-1]))]
    return tuple(sorted(n for bucket, count in zip(buckets, allocation)
                        for n in fisher_yates(bucket, count, rng)))


def combination_rank(pool: Sequence[int], k: int, rng: RandomSource) -> tuple[int, ...]:
    return unrank(pool, k, rng.randrange(comb(len(pool), k)))


SAMPLERS = dict(zip(UNIFORM_IDS, (
    fisher_yates, floyd, rejection, sequential, stratified, combination_rank,
)))


def frequency_weights(history: Sequence[Sequence[int]], *, window: int = 300,
                      prior_strength: int = 500, history_mix: float = 0.05) -> dict[int, int]:
    """Exact rational uniform/posterior mixture, used WITHOUT rank amplification.

    Each integer is proportional to (1-lambda)/45 + lambda * posterior_i/6.
    Sequential weighted draws are experimental personalization, not uniform.
    The weights are NOT the final without-replacement inclusion probabilities.
    """
    if type(window) is not int or window < 1 or type(prior_strength) is not int or prior_strength < 1:
        raise ValueError("Invalid Bayesian window/prior")
    if isinstance(history_mix, bool) or not 0 <= history_mix <= 0.10:
        raise ValueError("History mixture must be between 0 and 0.10")
    mix = Fraction(str(history_mix))
    rows = history[-window:]
    counts: Counter[int] = Counter()
    for row in rows:
        if len(validate_fixed(row)) != 6:
            raise ValueError("Invalid history draw")
        counts.update(row)
    a, b = mix.numerator, mix.denominator
    w = len(rows)
    return {n: (b - a) * 6 * (w + prior_strength)
            + a * (45 * counts[n] + prior_strength * 6) for n in NUMBERS}


def weighted_sample(pool: Sequence[int], k: int, rng: RandomSource,
                    weights: dict[int, int]) -> tuple[int, ...]:
    remaining, chosen = list(pool), []
    for _ in range(k):
        target = rng.randrange(sum(weights[n] for n in remaining))
        for index, number in enumerate(remaining):
            target -= weights[number]
            if target < 0:
                chosen.append(remaining.pop(index))
                break
    return tuple(sorted(chosen))


def _ac_filtered_ticket(pool: Sequence[int], k: int, fixed: tuple[int, ...],
                        blocked: set[tuple[int, ...]], rng: RandomSource) -> tuple[int, ...]:
    """Uniform on AC>=7 completions, conditional on success; never relax AC.

    Small fixed-number spaces are enumerated exactly. Large spaces use bounded
    iid rejection sampling. Exhausting retries is NOT proof of infeasibility.
    No score ranking, history weighting, or deterministic fill is permitted.
    """
    if comb(len(pool), k) <= AC_EXACT_SPACE_LIMIT:
        allowed = []
        for extra in combinations(pool, k):
            ticket = tuple(sorted((*fixed, *extra)))
            if ticket not in blocked and ac_value(ticket) >= AC_MINIMUM:
                allowed.append(ticket)
        if not allowed:
            raise ValueError("고정·제외번호와 AC 7 이상 조건을 만족하는 조합이 없습니다")
        return allowed[rng.randrange(len(allowed))]
    for _ in range(AC_MAX_ATTEMPTS):
        ticket = tuple(sorted((*fixed, *fisher_yates(pool, k, rng))))
        if ticket not in blocked and ac_value(ticket) >= AC_MINIMUM:
            return ticket
    raise ValueError("AC 공식의 재시도 상한에 도달했습니다. 조건을 완화하지 않았습니다")


def generate_ticket(formula_id: str, fixed_numbers: Iterable[int] = (), *,
                    excluded_combinations: Iterable[Sequence[int]] = (),
                    history: Sequence[Sequence[int]] = (),
                    rng: RandomSource | None = None) -> tuple[int, ...]:
    """Uniform on formula-allowed completions, except experimental Bayesian.

    Exclusions include only valid full tickets containing every fixed number.
    Exhausted spaces fail explicitly. Uniform rank fallback stays exact even
    with many exclusions; there is no lexicographic/score-based fallback bias.
    AC adds an explicit shape restriction and never uses unrestricted fallback.
    """
    if formula_id not in SAMPLERS and formula_id not in (BAYESIAN_ID, AC_FILTER_ID, "crowd_pattern_avoidance", *CUSTOM_IDS):
        raise ValueError("Unknown sampling formula")
    if formula_id == "constraint_uniform":
        from .constraints import generate
        return generate({"fixed": list(fixed_numbers)}, previous=history[-1] if history else (),
                        blocked=excluded_combinations, rng=rng)
    fixed = validate_fixed(fixed_numbers)
    fixed_set = set(fixed)
    pool = tuple(n for n in NUMBERS if n not in fixed_set)
    k = 6 - len(fixed)
    blocked = set()
    for values in excluded_combinations:
        ticket = validate_fixed(values)
        if len(ticket) != 6:
            raise ValueError("Exclusion must contain six numbers")
        if fixed_set.issubset(ticket):
            blocked.add(ticket)
    total = comb(len(pool), k)
    if len(blocked) >= total:
        raise ValueError("고정번호와 제외 조건을 만족하는 새 조합이 없습니다")
    rng = rng if rng is not None else SystemRandom()
    if formula_id == "crowd_pattern_avoidance":
        from .preference import select_ticket
        return select_ticket(fixed, blocked, rng)
    if formula_id == AC_FILTER_ID:
        return _ac_filtered_ticket(pool, k, fixed, blocked, rng)
    weights = frequency_weights(history) if formula_id == BAYESIAN_ID else None
    for _ in range(64):
        extra = (weighted_sample(pool, k, rng, weights) if weights is not None
                 else SAMPLERS[formula_id](pool, k, rng))
        ticket = tuple(sorted((*fixed, *extra)))
        if ticket not in blocked:
            return ticket
    if weights is not None:
        raise ValueError("빈도 공식의 제외 조건이 너무 강합니다. 균등 공식을 사용하세요")
    forbidden_ranks = sorted(rank_subset(pool, tuple(n for n in t if n not in fixed_set))
                             for t in blocked)
    rank = rng.randrange(total - len(forbidden_ranks))
    for forbidden in forbidden_ranks:
        if forbidden > rank:
            break
        rank += 1
    return tuple(sorted((*fixed, *unrank(pool, k, rank))))
