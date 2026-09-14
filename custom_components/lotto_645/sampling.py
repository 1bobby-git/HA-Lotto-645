"""Auditable Lotto 6/45 samplers; no prediction, filters or HA dependencies.

Production uses OS-backed SystemRandom; seeded RNG injection is for tests only.
All five uniform algorithms sample the same distribution. Fixed numbers limit
that statement to the conditional space. Rejecting past draws or ranking the
result afterwards changes the sample space and must be disclosed separately.
"""
from __future__ import annotations

from bisect import bisect_right
from functools import lru_cache
from itertools import accumulate
from math import comb
from secrets import SystemRandom
from typing import Iterable, Mapping, Protocol, Sequence


class IntegerRNG(Protocol):
    """The only randomness primitive required by the samplers."""

    def randrange(self, stop: int) -> int: ...


FORMULA_FISHER_YATES = "uniform_fisher_yates"
FORMULA_FLOYD = "uniform_floyd"
FORMULA_REJECTION = "uniform_rejection"
FORMULA_SEQUENTIAL = "uniform_sequential"
FORMULA_CCSS = "calibrated_stratified"
UNIFORM_FORMULA_IDS = (
    FORMULA_FISHER_YATES, FORMULA_FLOYD, FORMULA_REJECTION,
    FORMULA_SEQUENTIAL, FORMULA_CCSS,
)
FORMULA_VERSION = 1
BUCKETS = (tuple(range(1, 11)), tuple(range(11, 21)), tuple(range(21, 31)),
           tuple(range(31, 41)), tuple(range(41, 46)))
HISTORY_LOOKBACK = 300
PRIOR_STRENGTH = 500
HISTORY_MIX_PERCENT = 5
MAX_HISTORY_MIX_PERCENT = 10


def validate_fixed_numbers(values: Iterable[int] = ()) -> tuple[int, ...]:
    """Reject coercion (bool/float/string), duplicates and out-of-range values."""
    numbers = tuple(values)
    if len(numbers) > 6 or any(type(n) is not int or not 1 <= n <= 45 for n in numbers):
        raise ValueError("고정번호는 1~45의 정수로 최대 6개까지 지정할 수 있습니다.")
    if len(set(numbers)) != len(numbers):
        raise ValueError("고정번호를 중복 지정할 수 없습니다.")
    return tuple(sorted(numbers))


def fisher_yates(pool: Sequence[int], count: int, rng: IntegerRNG) -> list[int]:
    """Partial Fisher-Yates: one unbiased integer draw per chosen element."""
    values = list(pool)
    for index in range(count):
        other = index + rng.randrange(len(values) - index)
        values[index], values[other] = values[other], values[index]
    return values[:count]


def floyd(pool: Sequence[int], count: int, rng: IntegerRNG) -> list[int]:
    """Floyd's collision branch inserts j, not a second random index."""
    chosen: set[int] = set()
    for index in range(len(pool) - count, len(pool)):
        candidate = rng.randrange(index + 1)
        chosen.add(index if candidate in chosen else candidate)
    return [pool[index] for index in sorted(chosen)]


def rejection(pool: Sequence[int], count: int, rng: IntegerRNG) -> list[int]:
    """Duplicate rejection with a bounded, still-uniform completion path.

    A defective injected RNG must not hang HA. After 256 attempts, fill from
    the unused pool with Fisher-Yates. For an unbiased RNG this preserves the
    uniform distribution (conditional on the uniformly selected partial set).
    """
    chosen: set[int] = set()
    for _ in range(256):
        if len(chosen) == count:
            return sorted(chosen)
        chosen.add(pool[rng.randrange(len(pool))])
    remaining = [number for number in pool if number not in chosen]
    return sorted(chosen.union(fisher_yates(remaining, count - len(chosen), rng)))


def sequential(pool: Sequence[int], count: int, rng: IntegerRNG) -> list[int]:
    """Sequential inclusion using randrange(m) < r, never float r/m."""
    chosen = []
    for index, number in enumerate(pool):
        needed = count - len(chosen)
        if not needed:
            break
        left = len(pool) - index
        if needed == left:
            chosen.extend(pool[index:])
            break
        if rng.randrange(left) < needed:
            chosen.append(number)
    return chosen


@lru_cache(maxsize=128)
def allocation_table(capacities: tuple[int, ...], count: int) -> tuple[
    tuple[tuple[int, ...], ...], tuple[int, ...]
]:
    """Return CCSS allocations and exact cumulative integer combination counts."""
    if not capacities or count < 0 or any(c < 0 for c in capacities) or count > sum(capacities):
        raise ValueError("Invalid stratification capacities")
    allocations: list[tuple[int, ...]] = []
    weights: list[int] = []

    def walk(index: int, left: int, prefix: tuple[int, ...], weight: int) -> None:
        if index == len(capacities) - 1:
            if left <= capacities[index]:
                allocations.append((*prefix, left))
                weights.append(weight * comb(capacities[index], left))
            return
        for size in range(min(capacities[index], left) + 1):
            walk(index + 1, left - size, (*prefix, size), weight * comb(capacities[index], size))

    walk(0, count, (), 1)
    cumulative = tuple(accumulate(weights))
    if not cumulative or cumulative[-1] != comb(sum(capacities), count):
        raise RuntimeError("CCSS partition does not cover the conditional space")
    return tuple(allocations), cumulative


def calibrated_stratified(pool: Sequence[int], count: int, rng: IntegerRNG) -> list[int]:
    """Choose a stratum by its exact cardinality, then sample within it."""
    available = set(pool)
    buckets = [tuple(n for n in bucket if n in available) for bucket in BUCKETS]
    allocations, cumulative = allocation_table(tuple(map(len, buckets)), count)
    allocation = allocations[bisect_right(cumulative, rng.randrange(cumulative[-1]))]
    return [number for bucket, size in zip(buckets, allocation)
            for number in fisher_yates(bucket, size, rng)]


_SAMPLERS = dict(zip(UNIFORM_FORMULA_IDS, (
    fisher_yates, floyd, rejection, sequential, calibrated_stratified,
)))


def sample_uniform(formula_id: str = FORMULA_CCSS, *, fixed_numbers: Iterable[int] = (),
                   rng: IntegerRNG | None = None) -> tuple[int, ...]:
    """Generate one uniform valid ticket, conditionally on explicit fixed numbers."""
    if formula_id not in _SAMPLERS:
        raise ValueError("Unknown uniform formula")
    fixed = validate_fixed_numbers(fixed_numbers)
    if len(fixed) == 6:
        return fixed
    source = rng if rng is not None else SystemRandom()
    pool = [number for number in range(1, 46) if number not in fixed]
    extra = _SAMPLERS[formula_id](pool, 6 - len(fixed), source)
    return tuple(sorted((*fixed, *extra)))


def posterior_weights(frequencies: Mapping[int, int], draw_count: int, *,
                      prior_strength: int = PRIOR_STRENGTH,
                      history_mix_percent: int = HISTORY_MIX_PERCENT) -> tuple[int, ...]:
    """Exact integer weights for a Beta posterior mixed with uniform weights.

    posterior_i = (f_i + kappa*6/45)/(W+kappa)
    weight_i = (1-lambda)/45 + lambda*posterior_i/6

    Returned weights share one denominator, so integer cumulative sampling is
    exact. They are NOT the final inclusion probabilities after weighted
    sampling without replacement. This is experimental personalization only.
    """
    if type(draw_count) is not int or draw_count < 0:
        raise ValueError("Invalid history count")
    if type(prior_strength) is not int or prior_strength <= 0:
        raise ValueError("Prior strength must be a positive integer")
    if type(history_mix_percent) is not int or not 0 <= history_mix_percent <= MAX_HISTORY_MIX_PERCENT:
        raise ValueError("History mixture must be between 0 and 10 percent")
    if any(type(n) is not int or not 1 <= n <= 45 or type(f) is not int or not 0 <= f <= draw_count
           for n, f in frequencies.items()) or sum(frequencies.values()) != 6 * draw_count:
        raise ValueError("History frequencies must describe valid six-number draws")
    base = 6 * (100 * prior_strength + (100 - history_mix_percent) * draw_count)
    return tuple(base + 45 * history_mix_percent * frequencies.get(n, 0) for n in range(1, 46))


def sample_bayesian(frequencies: Mapping[int, int], draw_count: int, *,
                    fixed_numbers: Iterable[int] = (), rng: IntegerRNG | None = None,
                    prior_strength: int = PRIOR_STRENGTH,
                    history_mix_percent: int = HISTORY_MIX_PERCENT) -> tuple[int, ...]:
    """Weakly weighted sampling without replacement, not top-score ranking."""
    weights = posterior_weights(frequencies, draw_count, prior_strength=prior_strength,
                                history_mix_percent=history_mix_percent)
    chosen = list(validate_fixed_numbers(fixed_numbers))
    source = rng if rng is not None else SystemRandom()
    pool = [n for n in range(1, 46) if n not in chosen]
    while len(chosen) < 6:
        cumulative = list(accumulate(weights[n - 1] for n in pool))
        index = bisect_right(cumulative, source.randrange(cumulative[-1]))
        chosen.append(pool.pop(index))
    return tuple(sorted(chosen))
