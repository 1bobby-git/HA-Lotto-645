"""Selectable Lotto 6/45 heuristic analysis engine.

The engine converts complete historical results into multi-timescale residual,
transition, co-occurrence, recency, recurrence-gap, balance, delta, carry-over,
and optional traditional East-Asian calendrical/five-element features.

Every profile is a selection heuristic only. It does not change the probability
of an individual six-number combination.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from itertools import combinations
from heapq import heappush, heapreplace
import math
from statistics import fmean, median
from typing import Any

from .const import DISCLAIMER, FIRST_PRIZE_ODDS, PUBLIC_FORMULA_NOTICE
from .methods import (
    DEFAULT_METHOD_IDS,
    METHOD_BALANCE,
    METHOD_BAYESIAN_SHRINKAGE,
    METHOD_CARRYOVER,
    METHOD_CYCLE_RHYTHM,
    METHOD_DELTA,
    METHOD_HOT_NUMBERS,
    METHOD_MULTISCALE_RESONANCE,
    METHOD_MYUNGRI_HETU,
    METHOD_OVERDUE_GAP,
    METHOD_PAIR_COOCCURRENCE,
    METHOD_PHASE_RESIDUAL,
    METHOD_PUBLIC_ENSEMBLE,
    METHOD_SELECTED_MEDIAN,
    METHOD_RECENCY_DECAY,
    METHOD_TRANSITION_GAP,
    METHOD_TRIPLET_COOCCURRENCE,
    METHOD_WEIGHTED_FREQUENCY,
    METHODS_BY_ID,
    MethodDefinition,
    normalize_method_ids,
    consensus_source_ids,
)
from .consensus import refresh_consensus
from .sampling import generate_ticket, validate_fixed
from .models import AnalysisResult, LottoDraw, Recommendation
from .myungri import build_myungri_context, combo_myungri_details, combo_myungri_score

NUMBERS = tuple(range(1, 46))
DRAW_SIZE = 6
NUMBER_PROBABILITY = DRAW_SIZE / 45
PAIR_PROBABILITY = (6 / 45) * (5 / 44)
TRIPLET_PROBABILITY = PAIR_PROBABILITY * (4 / 43)


def _count_window(history: list[LottoDraw], size: int) -> Counter[int]:
    rows = history[-min(size, len(history)) :]
    counts: Counter[int] = Counter()
    for draw in rows:
        counts.update(draw.numbers)
    return counts


def _z_residual(count: float, trials: int, probability: float) -> float:
    if trials <= 0:
        return 0.0
    expected = trials * probability
    variance = trials * probability * (1.0 - probability)
    if variance <= 0:
        return 0.0
    return (count - expected) / math.sqrt(variance)


def _rank01(values: dict[int, float]) -> dict[int, float]:
    """Average-rank ties; equal evidence must not favor a larger ball number."""
    if any(not math.isfinite(value) for value in values.values()):
        raise ValueError("분석 지표에 유효하지 않은 숫자가 있습니다")
    ordered = sorted(values, key=lambda number: (values[number], number))
    if len(ordered) <= 1:
        return {number: 0.5 for number in ordered}
    result: dict[int, float] = {}
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        rank = (start + end - 1) / (2 * (len(ordered) - 1))
        for number in ordered[start:end]:
            result[number] = rank
        start = end
    return result


def _bayesian_feature(values: dict[int, float]) -> dict[int, float]:
    """Keep posterior effect size: rank-transforming would undo shrinkage."""
    return {number: 0.5 + 0.5 * math.tanh(value / NUMBER_PROBABILITY)
            for number, value in values.items()}


def _gap_since_last(history: list[LottoDraw], number: int) -> int:
    for gap, draw in enumerate(reversed(history)):
        if number in draw.numbers:
            return gap
    return len(history)


def _transition_scores(history: list[LottoDraw]) -> dict[int, float]:
    latest = history[-1]
    values = {number: 0.0 for number in NUMBERS}
    used_sources = 0
    for source in latest.numbers:
        trials = 0
        next_counts: Counter[int] = Counter()
        for index in range(len(history) - 1):
            if source in history[index].numbers:
                trials += 1
                next_counts.update(history[index + 1].numbers)
        if trials == 0:
            continue
        used_sources += 1
        for number in NUMBERS:
            values[number] += _z_residual(next_counts[number], trials, NUMBER_PROBABILITY)
    if used_sources:
        for number in NUMBERS:
            values[number] /= used_sources
    return values


def _pair_graph(history: list[LottoDraw]) -> tuple[dict[tuple[int, int], float], dict[int, float]]:
    total_counts: Counter[tuple[int, int]] = Counter()
    recent_counts: Counter[tuple[int, int]] = Counter()
    recent = history[-min(120, len(history)) :]
    for draw in history:
        total_counts.update(combinations(draw.numbers, 2))
    for draw in recent:
        recent_counts.update(combinations(draw.numbers, 2))

    graph: dict[tuple[int, int], float] = {}
    edges_by_number: defaultdict[int, list[float]] = defaultdict(list)
    for pair in combinations(NUMBERS, 2):
        long_z = _z_residual(total_counts[pair], len(history), PAIR_PROBABILITY)
        recent_z = _z_residual(recent_counts[pair], len(recent), PAIR_PROBABILITY)
        edge = 0.68 * math.tanh(long_z / 3.0) + 0.32 * math.tanh(recent_z / 2.2)
        graph[pair] = edge
        positive = max(edge, 0.0)
        edges_by_number[pair[0]].append(positive)
        edges_by_number[pair[1]].append(positive)

    strength: dict[int, float] = {}
    for number in NUMBERS:
        strongest = sorted(edges_by_number[number], reverse=True)[:6]
        strength[number] = fmean(strongest) if strongest else 0.0
    return graph, strength


def _triplet_graph(history: list[LottoDraw]) -> tuple[dict[tuple[int, int, int], float], dict[int, float]]:
    total_counts: Counter[tuple[int, int, int]] = Counter()
    recent_counts: Counter[tuple[int, int, int]] = Counter()
    recent = history[-min(180, len(history)) :]
    for draw in history:
        total_counts.update(combinations(draw.numbers, 3))
    for draw in recent:
        recent_counts.update(combinations(draw.numbers, 3))

    graph: dict[tuple[int, int, int], float] = {}
    by_number: defaultdict[int, list[float]] = defaultdict(list)
    for triplet in combinations(NUMBERS, 3):
        long_z = _z_residual(total_counts[triplet], len(history), TRIPLET_PROBABILITY)
        recent_z = _z_residual(recent_counts[triplet], len(recent), TRIPLET_PROBABILITY)
        value = 0.72 * math.tanh(long_z / 3.2) + 0.28 * math.tanh(recent_z / 2.4)
        graph[triplet] = value
        positive = max(value, 0.0)
        for number in triplet:
            by_number[number].append(positive)

    strength: dict[int, float] = {}
    for number in NUMBERS:
        strongest = sorted(by_number[number], reverse=True)[:10]
        strength[number] = fmean(strongest) if strongest else 0.0
    return graph, strength


def _decayed_frequency(history: list[LottoDraw], half_life: float = 20.0) -> dict[int, float]:
    weighted = {number: 0.0 for number in NUMBERS}
    total_weight = 0.0
    ln2 = math.log(2.0)
    for age, draw in enumerate(reversed(history[-min(260, len(history)) :])):
        weight = math.exp(-ln2 * age / half_life)
        total_weight += weight
        for number in draw.numbers:
            weighted[number] += weight
    if total_weight <= 0:
        return weighted
    return {number: weighted[number] / total_weight - NUMBER_PROBABILITY for number in NUMBERS}


def _bayesian_recent(history: list[LottoDraw], window: int = 300, prior_strength: float = 500.0) -> dict[int, float]:
    rows = history[-min(window, len(history)) :]
    counts: Counter[int] = Counter()
    for draw in rows:
        counts.update(draw.numbers)
    prior_success = prior_strength * NUMBER_PROBABILITY
    denominator = len(rows) + prior_strength
    return {
        number: (counts[number] + prior_success) / denominator - NUMBER_PROBABILITY
        for number in NUMBERS
    }


def _cycle_fit(history: list[LottoDraw], current_gaps: dict[int, int]) -> dict[int, float]:
    occurrences: dict[int, list[int]] = {number: [] for number in NUMBERS}
    for index, draw in enumerate(history):
        for number in draw.numbers:
            occurrences[number].append(index)
    result: dict[int, float] = {}
    for number in NUMBERS:
        points = occurrences[number]
        intervals = [points[i] - points[i - 1] for i in range(1, len(points))]
        if not intervals:
            result[number] = 0.0  # no observed cycle; neutral, not an invented 7-day cycle
            continue
        typical = float(median(intervals))
        distance = abs((current_gaps[number] + 1) - typical)
        result[number] = -distance / max(typical, 1.0)
    return result


def _feature_maps(
    history: list[LottoDraw],
    saju_profile: dict[str, Any] | None = None,
) -> tuple[dict[str, dict[int, float]], dict[str, Any]]:
    n = len(history)
    windows = (10, 30, 100, 120, 260)
    counts = {size: _count_window(history, size) for size in windows}
    count_long = _count_window(history, n)

    z_by_window: dict[int, dict[int, float]] = {}
    for size in windows:
        trials = min(size, n)
        z_by_window[size] = {
            number: _z_residual(counts[size][number], trials, NUMBER_PROBABILITY)
            for number in NUMBERS
        }

    z_long = {number: _z_residual(count_long[number], n, NUMBER_PROBABILITY) for number in NUMBERS}
    z10, z30, z100, z120, z260 = (z_by_window[x] for x in windows)
    velocity = {number: z30[number] - z120[number] for number in NUMBERS}
    curvature = {
        number: abs((z30[number] - z120[number]) - (z120[number] - z260[number]))
        for number in NUMBERS
    }
    counter_phase = {
        number: max(0.0, -(z_long[number] * velocity[number])) for number in NUMBERS
    }

    expected_gap = (1.0 - NUMBER_PROBABILITY) / NUMBER_PROBABILITY
    gap_sd = math.sqrt((1.0 - NUMBER_PROBABILITY) / (NUMBER_PROBABILITY**2))
    raw_gap = {number: _gap_since_last(history, number) for number in NUMBERS}
    gap_z = {number: (raw_gap[number] - expected_gap) / gap_sd for number in NUMBERS}
    gap_surprise = {number: min(abs(gap_z[number]), 2.5) for number in NUMBERS}
    gap_balance = {number: -abs(gap_z[number]) for number in NUMBERS}
    overdue_capped = {number: min(max(gap_z[number], -0.5), 2.4) for number in NUMBERS}

    transition = _transition_scores(history)
    pair_graph, graph_strength = _pair_graph(history)
    triplet_graph, triplet_strength = _triplet_graph(history)
    decay_frequency = _decayed_frequency(history)
    bayesian_60 = _bayesian_recent(history)
    cycle_fit = _cycle_fit(history, raw_gap)
    myungri = build_myungri_context(history[-1].draw_date, saju_profile)

    raw_features = {
        "counter_phase": counter_phase,
        "phase_velocity": {number: abs(velocity[number]) for number in NUMBERS},
        "phase_velocity_positive": velocity,
        "transition": transition,
        "curvature": curvature,
        "gap_surprise": gap_surprise,
        "gap_balance": gap_balance,
        "overdue_capped": overdue_capped,
        "graph_strength": graph_strength,
        "triplet_strength": triplet_strength,
        "frequency_decay": decay_frequency,
        "bayesian_60": bayesian_60,
        "cycle_fit": cycle_fit,
        "long_neutral": {number: -abs(z_long[number]) for number in NUMBERS},
        "recent_neutral": {number: -abs(z30[number]) for number in NUMBERS},
        "frequency_10": z10,
        "frequency_30": z30,
        "frequency_100": z100,
        "frequency_long": z_long,
        "myungri_resonance": dict(myungri["number_resonance"]),
    }
    ranked = {name: _rank01(values) for name, values in raw_features.items()}
    ranked["bayesian_60"] = _bayesian_feature(bayesian_60)
    ranked["myungri_resonance"] = dict(myungri["number_resonance"])
    # Missing recurrence observations are neutral even among observed cycles.
    for number in NUMBERS:
        if count_long[number] < 2:
            ranked["cycle_fit"][number] = 0.5
    context = {
        "z_long": z_long,
        "z10": z10,
        "z30": z30,
        "z100": z100,
        "z120": z120,
        "velocity": velocity,
        "transition_raw": transition,
        "gap": raw_gap,
        "gap_z": gap_z,
        "pair_graph": pair_graph,
        "graph_strength_raw": graph_strength,
        "triplet_graph": triplet_graph,
        "triplet_strength_raw": triplet_strength,
        "ranked": ranked,
        "myungri": myungri,
    }
    return ranked, context


def _method_number_scores(method: MethodDefinition, ranked: dict[str, dict[int, float]]) -> dict[int, float]:
    return {
        number: sum(weight * ranked[feature][number] for feature, weight in method.weights.items())
        / sum(method.weights.values())
        for number in NUMBERS
    }


def _combo_diversity(combo: tuple[int, ...], velocity: dict[int, float]) -> float:
    signs = [1.0 if velocity[number] >= 0 else -1.0 for number in combo]
    phase_mix = 1.0 - abs(fmean(signs))
    gaps = [combo[index + 1] - combo[index] for index in range(len(combo) - 1)]
    mean_gap = fmean(gaps)
    spread = math.sqrt(fmean((gap - mean_gap) ** 2 for gap in gaps))
    spacing_mix = min(spread / 7.0, 1.0)
    return 0.62 * phase_mix + 0.38 * spacing_mix


def _balance_score(combo: tuple[int, ...]) -> float:
    odd_count = sum(number % 2 for number in combo)
    low_count = sum(number <= 22 for number in combo)
    total = sum(combo)
    span = combo[-1] - combo[0]
    sections = len({min((number - 1) // 10, 4) for number in combo})
    odd_score = max(0.0, 1.0 - abs(odd_count - 3) / 3)
    low_score = max(0.0, 1.0 - abs(low_count - 3) / 3)
    sum_score = max(0.0, 1.0 - abs(total - 138) / 72)
    span_score = max(0.0, 1.0 - abs(span - 34) / 28)
    section_score = min(sections / 5.0, 1.0)
    return 0.23 * odd_score + 0.23 * low_score + 0.24 * sum_score + 0.15 * span_score + 0.15 * section_score


def _delta_score(combo: tuple[int, ...]) -> float:
    deltas = [combo[0]] + [combo[index] - combo[index - 1] for index in range(1, len(combo))]
    within_15 = sum(1 <= delta <= 15 for delta in deltas) / len(deltas)
    uniqueness = len(set(deltas)) / len(deltas)
    repeated_penalty = max(0, max(Counter(deltas).values()) - 2) / 4
    max_delta_score = max(0.0, 1.0 - abs(max(deltas) - 11) / 18)
    range_score = max(0.0, 1.0 - abs((combo[-1] - combo[0]) - 34) / 30)
    return max(0.0, 0.42 * within_15 + 0.21 * uniqueness + 0.18 * max_delta_score + 0.19 * range_score - 0.20 * repeated_penalty)


def match_probability(matches: int) -> float:
    """Exact overlap-category mass for two 6-subsets of 45, not ticket odds."""
    if not 0 <= matches <= DRAW_SIZE:
        return 0.0
    return math.comb(6, matches) * math.comb(39, 6 - matches) / math.comb(45, 6)


_CARRYOVER_MASSES = tuple(match_probability(k) for k in range(7))


def _carryover_score(combo: tuple[int, ...], latest_numbers: set[int]) -> float:
    overlap = len(set(combo) & latest_numbers)
    return _CARRYOVER_MASSES[overlap] / max(_CARRYOVER_MASSES)


def _component_weights(method: MethodDefinition) -> dict[str, float]:
    weights = {
        "individual": 0.66, "pair": method.pair_weight,
        "triplet": method.triplet_weight, "diversity": method.diversity_weight,
        "balance": method.balance_weight, "delta": method.delta_weight,
        "carryover": method.carryover_weight, "myungri": method.myungri_weight,
    }
    total = sum(weights.values())
    return {key: value / total for key, value in weights.items() if value}


def _build_seen_subset_counts(history: list[LottoDraw]) -> tuple[Counter[tuple[int, ...]], Counter[tuple[int, ...]]]:
    quads: Counter[tuple[int, ...]] = Counter()
    quints: Counter[tuple[int, ...]] = Counter()
    for draw in history:
        quads.update(combinations(draw.numbers, 4))
        quints.update(combinations(draw.numbers, 5))
    return quads, quints


def _score_components(combo: tuple[int, ...], number_scores: dict[int, float], method: MethodDefinition, context: dict[str, Any], latest_numbers: set[int]) -> dict[str, float]:
    pair_graph: dict[tuple[int, int], float] = context["pair_graph"]
    pair_values = [pair_graph[tuple(sorted(pair))] for pair in combinations(combo, 2)]
    triplet_value = 0.5
    if method.triplet_weight:
        triplet_graph: dict[tuple[int, int, int], float] = context["triplet_graph"]
        triplet_values = [triplet_graph[tuple(sorted(group))] for group in combinations(combo, 3)]
        triplet_value = (fmean(triplet_values) + 1.0) / 2.0
    return {
        "individual": fmean(number_scores[number] for number in combo),
        "pair": (fmean(pair_values) + 1.0) / 2.0,
        "triplet": triplet_value,
        "diversity": _combo_diversity(combo, context["velocity"]) if method.diversity_weight else 0.5,
        "balance": _balance_score(combo) if method.balance_weight else 0.5,
        "delta": _delta_score(combo) if method.delta_weight else 0.5,
        "carryover": _carryover_score(combo, latest_numbers) if method.carryover_weight else 0.5,
        "myungri": combo_myungri_score(combo, context["myungri"]) if method.myungri_weight else 0.5,
    }


def _combo_score(combo: tuple[int, ...], number_scores: dict[int, float], method: MethodDefinition, context: dict[str, Any], latest_numbers: set[int], quads: Counter[tuple[int, ...]], quints: Counter[tuple[int, ...]]) -> tuple[float, dict[str, float]]:
    components = _score_components(combo, number_scores, method, context, latest_numbers)
    latest_overlap = len(set(combo) & latest_numbers)
    repeated_quad = max((quads[subset] for subset in combinations(combo, 4)), default=0)
    repeated_quint = max((quints[subset] for subset in combinations(combo, 5)), default=0)
    latest_penalty_rate = 0.007 if method.carryover_weight else 0.023
    penalty = latest_penalty_rate * latest_overlap
    penalty += 0.012 * min(repeated_quad, 3)
    penalty += 0.026 * min(repeated_quint, 2)
    weights = context.get("component_weights") or _component_weights(method)
    score = max(0.0, min(1.0, sum(weights[key] * components[key] for key in weights) - penalty))
    components["historical_similarity_penalty"] = penalty
    return score, components


def _candidate_pool(method: MethodDefinition, number_scores: dict[int, float]) -> tuple[int, ...]:
    ordered = sorted(NUMBERS, key=lambda number: (-number_scores[number], number))
    base_count = max(14, method.pool_size - 10)
    selected: list[int] = ordered[:base_count]
    for start, end in ((1, 10), (11, 20), (21, 30), (31, 40), (41, 45)):
        bucket = [number for number in ordered if start <= number <= end]
        for number in bucket[:2]:
            if number not in selected:
                selected.append(number)
    for number in ordered:
        if len(selected) >= method.pool_size:
            break
        if number not in selected:
            selected.append(number)
    return tuple(sorted(selected[: method.pool_size]))


def _select_candidate(method: MethodDefinition, history: list[LottoDraw], ranked: dict[str, dict[int, float]], context: dict[str, Any], selected: list[tuple[int, ...]], past_combos: set[tuple[int, ...]], quads: Counter[tuple[int, ...]], quints: Counter[tuple[int, ...]], generation_nonce: int) -> tuple[tuple[int, ...], float, dict[str, float]]:
    """Bounded top-k search; never fall back to a duplicate or a prior ticket."""
    number_scores = _method_number_scores(method, ranked)
    pool = _candidate_pool(method, number_scores)
    latest_numbers = set(history[-1].numbers)
    forbidden = past_combos | set(selected) | set(context.get("excluded_combinations", ()))
    context["component_weights"] = _component_weights(method)
    heap: list[tuple[float, tuple[int, ...], tuple[int, ...]]] = []
    for combo in combinations(pool, 6):
        if combo in forbidden:
            continue
        score, _ = _combo_score(combo, number_scores, method, context, latest_numbers, quads, quints)
        # Negative tuple retains the old deterministic preference for small tuples
        # only as a documented tie-break, not as fake evidence in feature ranks.
        item = (score, tuple(-number for number in combo), combo)
        if len(heap) < 1200:
            heappush(heap, item)
        elif item > heap[0]:
            heapreplace(heap, item)
    scored = sorted(heap, reverse=True)
    if not scored:
        raise ValueError("이전 추천을 제외한 유효한 후보가 없습니다")
    usage = Counter(number for previous in selected for number in previous)
    qualified = []
    # A fixed global cap of 3 cannot hold for many selected methods. Relax
    # diversity explicitly; uniqueness and past-winner exclusions are never relaxed.
    for usage_cap in (3, max(4, len(selected) + 1)):
        for max_overlap in (3, 4, 5):
            qualified = [item for item in scored
                         if all(usage[number] < usage_cap for number in item[2])
                         and all(len(set(item[2]) & set(previous)) <= max_overlap
                                 for previous in selected)][:64]
            if qualified:
                break
        if qualified:
            break
    if not qualified:
        qualified = scored[:64]  # already filtered for all hard exclusions
    index = 0
    if generation_nonce > 0 and len(qualified) > 1:
        window = min(len(qualified), 48)
        offset = sum(ord(char) for char in method.method_id) % (window - 1)
        index = 1 + ((generation_nonce - 1 + offset) % (window - 1))
    score, _, combo = qualified[index]
    _, components = _combo_score(combo, number_scores, method, context, latest_numbers, quads, quints)
    return combo, score, components


def _max_past_overlap(combo: tuple[int, ...], history: Iterable[LottoDraw]) -> int:
    values = set(combo)
    return max((len(values & set(draw.numbers)) for draw in history), default=0)


def _strongest_pair(combo: tuple[int, ...], context: dict[str, Any]) -> tuple[tuple[int, int], float]:
    pair_graph: dict[tuple[int, int], float] = context["pair_graph"]
    return max(((tuple(sorted(pair)), pair_graph[tuple(sorted(pair))]) for pair in combinations(combo, 2)), key=lambda item: (item[1], tuple(-number for number in item[0])))


def _recommendation_reason(method: MethodDefinition, combo: tuple[int, ...], context: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    velocity: dict[int, float] = context["velocity"]
    transition: dict[int, float] = context["transition_raw"]
    gap: dict[int, int] = context["gap"]
    phase_leaders = sorted(combo, key=lambda n: (-abs(velocity[n]), n))[:2]
    transition_leaders = sorted(combo, key=lambda n: (-transition[n], n))[:2]
    hot_leaders = sorted(combo, key=lambda n: (-velocity[n], n))[:2]
    overdue_leaders = sorted(combo, key=lambda n: (-gap[n], n))[:2]
    pair, pair_value = _strongest_pair(combo, context)

    if method.method_id == METHOD_MYUNGRI_HETU:
        meta = context["myungri"]
        favorable = "·".join(meta.get("favorable_elements_ko", [])) or "보완오행"
        interactions = meta.get("interactions", {})
        positive_count = len(interactions.get("stem_harmony", [])) + len(interactions.get("branch_harmony", []))
        negative_count = len(interactions.get("stem_clash", [])) + len(interactions.get("branch_clash_harm_punishment", []))
        reason = (
            f"개인 원국 일간 {meta.get('day_master') or '-'}({meta.get('day_master_element_ko') or '-'}), "
            f"{meta.get('strength') or '강약 미정'} 기준 보완오행 {favorable}; "
            f"대운과 {meta.get('target_draw_date') or '다음 추첨일'} 사주의 합계열 {positive_count}건·충해형 {negative_count}건, "
            f"하도 수리오행 및 {pair[0]}-{pair[1]} 통계 연결을 보조 반영"
        )
    else:
        reasons = {
            METHOD_PHASE_RESIDUAL: f"장·단기 잔차 방향 변화가 큰 {phase_leaders[0]}·{phase_leaders[1]}, 전이 상위 {transition_leaders[0]}, 강한 연결 {pair[0]}-{pair[1]} 반영",
            METHOD_TRANSITION_GAP: f"다음 회차 전이 상위 {transition_leaders[0]}·{transition_leaders[1]}와 미출현 간격·시간축 곡률, {pair[0]}-{pair[1]} 연결을 결합",
            METHOD_MULTISCALE_RESONANCE: f"여러 시간대의 변화가 동시에 강한 {phase_leaders[0]}·{phase_leaders[1]}와 전이·그래프·간격을 공명 점수로 결합",
            METHOD_WEIGHTED_FREQUENCY: f"최근 10·30·100회 및 전체 빈도를 가중 합산하고 {pair[0]}-{pair[1]} 동반출현과 구간 균형을 보정",
            METHOD_HOT_NUMBERS: f"선택 조합 내 최근 출현 변화가 높은 {hot_leaders[0]}·{hot_leaders[1]}를 중심으로 핫넘버 집중과 번호대 쏠림을 함께 제어",
            METHOD_OVERDUE_GAP: f"현재 미출현 간격이 긴 {overdue_leaders[0]}·{overdue_leaders[1]}를 포함하되 콜드넘버 과집중과 장기 극단값을 제한",
            METHOD_PAIR_COOCCURRENCE: f"전체+최근 120회 동반출현 그래프 중심 조합이며 가장 강한 내부 연결은 {pair[0]}-{pair[1]}",
            METHOD_TRIPLET_COOCCURRENCE: f"세 번호 동시출현 구조와 2개 번호 연결을 함께 평가; 핵심 내부 연결 {pair[0]}-{pair[1]}",
            METHOD_RECENCY_DECAY: f"최근 회차에 큰 가중치를 주고 과거 영향은 지수적으로 줄여 최근성 중심 점수를 구성; {pair[0]}-{pair[1]} 연결 보정",
            METHOD_BAYESIAN_SHRINKAGE: f"최근 60회 출현률을 평균 6/45 쪽으로 수축해 작은 표본의 과대평가를 완화하고 {pair[0]}-{pair[1]} 연결을 보정",
            METHOD_CYCLE_RHYTHM: f"번호별 과거 재등장 간격의 중앙값과 현재 간격을 비교하고 전이·빈도·균형을 보조 적용",
            METHOD_BALANCE: f"번호합 {sum(combo)}, 홀수 {sum(n % 2 for n in combo)}개, 저구간 {sum(n <= 22 for n in combo)}개와 번호대 분산을 균형화",
            METHOD_DELTA: f"오름차순 번호 간 델타의 크기·반복·전체 범위를 평가하고 {pair[0]}-{pair[1]} 연결을 보조 반영",
            METHOD_CARRYOVER: f"직전 회차와 {len(set(combo) & set(context['latest_numbers']))}개 이월을 허용하고 전이 상위 {transition_leaders[0]}·{transition_leaders[1]}를 결합",
            METHOD_PUBLIC_ENSEMBLE: f"빈도·최근성·베이지안 수축·미출현·동반출현·균형·델타·이월수의 합의 점수; 핵심 연결 {pair[0]}-{pair[1]}, 번호합 {sum(combo)}",
        }
        reason = reasons[method.method_id]

    details: dict[str, Any] = {
        "method_description": method.description,
        "method_category": method.category,
        "phase_leaders": phase_leaders,
        "transition_leaders": transition_leaders,
        "strongest_pair": list(pair),
        "strongest_pair_score": round(pair_value, 4),
        "gaps_since_last": {str(number): gap[number] for number in combo},
        "number_sum": sum(combo),
        "odd_count": sum(number % 2 for number in combo),
        "low_count_1_22": sum(number <= 22 for number in combo),
        "carryover_count": len(set(combo) & set(context["latest_numbers"])),
    }
    if method.method_id == METHOD_MYUNGRI_HETU:
        details.update(combo_myungri_details(combo, context["myungri"]))
    return reason, details


def build_analysis(
    history: list[LottoDraw],
    method_ids: Sequence[str] | None = None,
    generation_nonce: int = 0,
    saju_profile: dict[str, Any] | None = None,
    excluded_combinations: Sequence[tuple[int, ...]] = (),
    restored_tickets: dict[str, tuple[int, ...]] | None = None,
    *, rng=None, progress_callback=None,
) -> AnalysisResult:
    """Build one recommendation per selected method.

    generation_nonce=0 returns the top deterministic candidates. Positive values
    deliberately rotate within each method's high-scoring candidate window so a
    manual refresh can regenerate local recommendations without touching AI.
    """
    if len(history) < 30:
        raise ValueError("분석에는 최소 30개 회차가 필요합니다")
    history = sorted(history, key=lambda draw: draw.round)
    expected_rounds = list(range(history[0].round, history[-1].round + 1))
    actual_rounds = [draw.round for draw in history]
    if history[0].round != 1 or actual_rounds != expected_rounds:
        raise ValueError("1회부터 최신 회차까지 연속된 전체 데이터가 필요합니다")

    selected_method_ids = (() if method_ids is not None and not method_ids else
                           normalize_method_ids(method_ids if method_ids is not None else DEFAULT_METHOD_IDS))
    for draw in history:
        if (len(draw.numbers) != 6 or len(set(draw.numbers)) != 6
                or any(type(number) is not int or not 1 <= number <= 45 for number in draw.numbers)
                or tuple(sorted(draw.numbers)) != tuple(draw.numbers)
                or type(draw.bonus) is not int or not 1 <= draw.bonus <= 45
                or draw.bonus in draw.numbers):
            raise ValueError("유효하지 않은 당첨 회차 데이터입니다")
    profile = saju_profile if METHOD_MYUNGRI_HETU in selected_method_ids else None
    ranked, context = _feature_maps(history, profile)
    if (METHOD_SELECTED_MEDIAN in selected_method_ids
            and len(consensus_source_ids(selected_method_ids)) < 2):
        raise ValueError("선택 공식 중앙값은 다른 로컬 추첨 공식을 2개 이상 함께 선택해야 합니다")
    context["excluded_combinations"] = tuple(tuple(sorted(combo)) for combo in excluded_combinations)
    if (
        METHOD_MYUNGRI_HETU in selected_method_ids
        and context["myungri"].get("status") != "ready"
    ):
        raise ValueError("명리 권장은 개인 사주정보 입력 후 사용할 수 있습니다")
    context["latest_numbers"] = list(history[-1].numbers)
    past_combos = {tuple(draw.numbers) for draw in history}
    quads, quints = _build_seen_subset_counts(history)

    restored_tickets = restored_tickets or {}
    selected: list[tuple[int, ...]] = []
    recommendations: list[Recommendation] = []
    execution_method_ids = tuple(
        method_id for method_id in selected_method_ids
        if method_id != METHOD_SELECTED_MEDIAN
    ) + ((METHOD_SELECTED_MEDIAN,) if METHOD_SELECTED_MEDIAN in selected_method_ids else ())
    for index, method_id in enumerate(execution_method_ids, start=1):
        method = METHODS_BY_ID[method_id]
        if progress_callback:
            progress_callback({"phase": "method_start", "method_id": method_id, "index": index})
        if method_id == METHOD_SELECTED_MEDIAN:
            if progress_callback:
                progress_callback({"phase": "method_complete", "method_id": method_id, "index": index})
            continue
        if method.sampling:
            blocked = past_combos | set(selected) | set(context["excluded_combinations"])
            # Reserve restored tickets belonging to later formulas as well.
            blocked.update(ticket for key, ticket in restored_tickets.items() if key != method_id)
            if method_id in restored_tickets:
                combo = validate_fixed(restored_tickets[method_id])
                if len(combo) != 6 or combo in blocked:
                    raise ValueError("저장된 추첨 공식 번호가 현재 제외 조건과 충돌합니다")
            else:
                combo = generate_ticket(method.sampling, excluded_combinations=blocked,
                                        history=[d.numbers for d in history], rng=rng)
            selected.append(combo)
            experimental = method_id == METHOD_BAYESIAN_SHRINKAGE
            details = {
                "formula_id": method_id, "formula_version": method.formula_version,
                "method_description": method.description, "method_category": method.category,
                "restored_from_cache": method_id in restored_tickets,
                "generation_sequence": generation_nonce, "rng": "injected_test_rng" if rng is not None else "system_csprng",
                "uniformity": "nonuniform_experimental" if experimental else "uniform_over_allowed_combinations",
                "eligible_combination_count": math.comb(45, 6) - len(blocked),
                "history_used_for_weighting": experimental, "history_cutoff_round": history[-1].round,
                "exclusions": "past_winning_combinations_and_duplicate_tickets",
                "exclusion_notice": "과거 제외는 당첨확률을 높이지 않으며 전체 조합 공간의 균등 추출과 다릅니다",
                "score_meaning": "난수 추출 결과에는 적합도 점수를 부여하지 않습니다",
                "validation_scope": "표본추출 구현 검증; 당첨 예측 검증이 아닙니다",
                "exact_past_first_prize_match": False,
                "max_numbers_matching_any_past_first_prize": _max_past_overlap(combo, history),
                "latest_draw_overlap": len(set(combo) & set(history[-1].numbers)),
                "number_sum": sum(combo), "odd_count": sum(n % 2 for n in combo),
                "first_prize_odds": FIRST_PRIZE_ODDS, "disclaimer": DISCLAIMER,
            }
            if experimental:
                details.update({"history_lookback": 300, "history_sample_size": min(300, len(history)),
                                "prior_strength": 500, "history_mix": 0.05})
            recommendations.append(Recommendation(index, method_id, method.label, method.category,
                                                 combo, method.description, None, details))
            if progress_callback:
                progress_callback({"phase": "method_complete", "method_id": method_id, "index": index})
            continue
        combo, score, components = _select_candidate(
            method, history, ranked, context, selected, past_combos | set(restored_tickets.values()), quads, quints, generation_nonce
        )
        selected.append(combo)
        reason, details = _recommendation_reason(method, combo, context)
        details.update(
            {
                "formula_id": method_id, "formula_version": method.formula_version,
                "uniformity": "nonuniform_personalization", "predictive_evidence": "not_established",
                "generation_sequence": generation_nonce,
                "score_components": {key: round(value, 4) for key, value in components.items()},
                "score_component_weights": {key: round(value, 6) for key, value in _component_weights(method).items()},
                "score_meaning": "0~1의 후보 적합도이며 당첨 확률이 아닙니다",
                "validation_scope": "계산 규칙 및 출력 조건 검증; 예측 효과 미입증",
                "number_feature_weights": {
                    key: round(value / sum(method.weights.values()), 6)
                    for key, value in method.weights.items()
                },
                "number_feature_scores": {
                    str(n): {key: round(ranked[key][n], 6) for key in method.weights}
                    for n in combo
                },
                "exact_past_first_prize_match": False,
                "max_numbers_matching_any_past_first_prize": _max_past_overlap(combo, history),
                "latest_draw_overlap": len(set(combo) & set(history[-1].numbers)),
            }
        )
        recommendations.append(
            Recommendation(
                index=index,
                method_id=method.method_id,
                label=method.label,
                method=method.category,
                numbers=combo,  # type: ignore[arg-type]
                reason=reason,
                score=score,
                details=details,
            )
        )

        if progress_callback:
            progress_callback({"phase": "method_complete", "method_id": method_id, "index": index})

    transition = context["transition_raw"]
    velocity = context["velocity"]
    graph_strength = context["graph_strength_raw"]
    triplet_strength = context["triplet_strength_raw"]
    myungri = context["myungri"]
    summary = {
        "algorithm": "research_formulas_v8_csprng_ccss",
        "generation_sequence": generation_nonce,
        "history_draws": len(history),
        "selected_method_ids": list(selected_method_ids),
        "selected_formula_ids": list(selected_method_ids),
        "execution_method_ids": list(execution_method_ids),
        "selected_methods": [
            {
                "method_id": method_id,
                "label": METHODS_BY_ID[method_id].label,
                "category": METHODS_BY_ID[method_id].category,
                "description": METHODS_BY_ID[method_id].description,
            }
            for method_id in selected_method_ids
        ],
        "top_phase_change": sorted(NUMBERS, key=lambda n: (-abs(velocity[n]), n))[:6],
        "top_transition": sorted(NUMBERS, key=lambda n: (-transition[n], n))[:6],
        "top_graph_strength": sorted(NUMBERS, key=lambda n: (-graph_strength[n], n))[:6],
        "top_triplet_strength": sorted(NUMBERS, key=lambda n: (-triplet_strength[n], n))[:6],
        "myungri_context": {
            "status": myungri.get("status"),
            "profile_configured": myungri.get("status") == "ready",
            "target_draw_date": myungri.get("target_draw_date"),
            "day_master": myungri.get("day_master"),
            "day_master_element": myungri.get("day_master_element_ko"),
            "day_master_strength": myungri.get("strength"),
            "favorable_elements": myungri.get("favorable_elements_ko"),
            "current_daewoon": myungri.get("luck_cycle", {}).get("current") if myungri.get("status") == "ready" else None,
            "target_interactions": myungri.get("interactions"),
            "notice": myungri.get("notice"),
            "privacy_notice": myungri.get("privacy_notice"),
        },
        "first_prize_odds": FIRST_PRIZE_ODDS,
        "public_formula_notice": PUBLIC_FORMULA_NOTICE,
        "disclaimer": DISCLAIMER,
    }
    result = AnalysisResult(
        target_round=history[-1].round + 1,
        based_on_round=history[-1].round,
        recommendations=tuple(recommendations),
        summary=summary,
    )
    return refresh_consensus(result, selected_method_ids, history)
