"""Deterministic, selectable Lotto 6/45 heuristic analysis engine.

The engine converts complete historical results into residual, transition,
co-occurrence, gap, balance, delta, and carry-over features. Public-formula
profiles are common analysis or filtering rules, not predictive mathematics.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from itertools import combinations
import math
from statistics import fmean
from typing import Any

from .const import DISCLAIMER, FIRST_PRIZE_ODDS, PUBLIC_FORMULA_NOTICE
from .methods import (
    DEFAULT_METHOD_IDS,
    METHOD_BALANCE,
    METHOD_CARRYOVER,
    METHOD_DELTA,
    METHOD_HOT_NUMBERS,
    METHOD_OVERDUE_GAP,
    METHOD_PAIR_COOCCURRENCE,
    METHOD_PHASE_RESIDUAL,
    METHOD_PUBLIC_ENSEMBLE,
    METHOD_TRANSITION_GAP,
    METHOD_WEIGHTED_FREQUENCY,
    METHODS_BY_ID,
    MethodDefinition,
    normalize_method_ids,
)
from .models import AnalysisResult, LottoDraw, Recommendation

NUMBERS = tuple(range(1, 46))
DRAW_SIZE = 6
NUMBER_PROBABILITY = DRAW_SIZE / 45
PAIR_PROBABILITY = (6 / 45) * (5 / 44)


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
    ordered = sorted(values, key=lambda number: (values[number], number))
    if len(ordered) <= 1:
        return {number: 0.5 for number in ordered}
    return {
        number: index / (len(ordered) - 1)
        for index, number in enumerate(ordered)
    }


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
            values[number] += _z_residual(
                next_counts[number], trials, NUMBER_PROBABILITY
            )
    if used_sources:
        for number in NUMBERS:
            values[number] /= used_sources
    return values


def _pair_graph(
    history: list[LottoDraw],
) -> tuple[dict[tuple[int, int], float], dict[int, float]]:
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
        recent_z = _z_residual(
            recent_counts[pair], len(recent), PAIR_PROBABILITY
        )
        edge = 0.68 * math.tanh(long_z / 3.0) + 0.32 * math.tanh(
            recent_z / 2.2
        )
        graph[pair] = edge
        positive = max(edge, 0.0)
        edges_by_number[pair[0]].append(positive)
        edges_by_number[pair[1]].append(positive)

    strength: dict[int, float] = {}
    for number in NUMBERS:
        strongest = sorted(edges_by_number[number], reverse=True)[:6]
        strength[number] = fmean(strongest) if strongest else 0.0
    return graph, strength


def _feature_maps(
    history: list[LottoDraw],
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
    z_long = {
        number: _z_residual(count_long[number], n, NUMBER_PROBABILITY)
        for number in NUMBERS
    }
    z10 = z_by_window[10]
    z30 = z_by_window[30]
    z100 = z_by_window[100]
    z120 = z_by_window[120]
    z260 = z_by_window[260]

    velocity = {number: z30[number] - z120[number] for number in NUMBERS}
    curvature = {
        number: abs(
            (z30[number] - z120[number])
            - (z120[number] - z260[number])
        )
        for number in NUMBERS
    }
    counter_phase = {
        number: max(0.0, -(z_long[number] * velocity[number]))
        for number in NUMBERS
    }

    expected_gap = (1.0 - NUMBER_PROBABILITY) / NUMBER_PROBABILITY
    gap_sd = math.sqrt(
        (1.0 - NUMBER_PROBABILITY) / (NUMBER_PROBABILITY**2)
    )
    raw_gap = {
        number: _gap_since_last(history, number) for number in NUMBERS
    }
    gap_z = {
        number: (raw_gap[number] - expected_gap) / gap_sd
        for number in NUMBERS
    }
    gap_surprise = {
        number: min(abs(gap_z[number]), 2.5) for number in NUMBERS
    }
    gap_balance = {number: -abs(gap_z[number]) for number in NUMBERS}
    overdue_capped = {
        number: min(max(gap_z[number], -0.5), 2.4) for number in NUMBERS
    }

    transition = _transition_scores(history)
    pair_graph, graph_strength = _pair_graph(history)

    raw_features = {
        "counter_phase": counter_phase,
        "phase_velocity": {
            number: abs(velocity[number]) for number in NUMBERS
        },
        "phase_velocity_positive": velocity,
        "transition": transition,
        "curvature": curvature,
        "gap_surprise": gap_surprise,
        "gap_balance": gap_balance,
        "overdue_capped": overdue_capped,
        "graph_strength": graph_strength,
        "long_neutral": {
            number: -abs(z_long[number]) for number in NUMBERS
        },
        "recent_neutral": {
            number: -abs(z30[number]) for number in NUMBERS
        },
        "frequency_10": z10,
        "frequency_30": z30,
        "frequency_100": z100,
        "frequency_long": z_long,
    }
    ranked = {
        name: _rank01(values) for name, values in raw_features.items()
    }
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
        "ranked": ranked,
    }
    return ranked, context


def _method_number_scores(
    method: MethodDefinition,
    ranked: dict[str, dict[int, float]],
) -> dict[int, float]:
    return {
        number: sum(
            weight * ranked[feature][number]
            for feature, weight in method.weights.items()
        )
        for number in NUMBERS
    }


def _combo_diversity(
    combo: tuple[int, ...], velocity: dict[int, float]
) -> float:
    signs = [1.0 if velocity[number] >= 0 else -1.0 for number in combo]
    phase_mix = 1.0 - abs(fmean(signs))
    gaps = [
        combo[index + 1] - combo[index]
        for index in range(len(combo) - 1)
    ]
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
    return (
        0.23 * odd_score
        + 0.23 * low_score
        + 0.24 * sum_score
        + 0.15 * span_score
        + 0.15 * section_score
    )


def _delta_score(combo: tuple[int, ...]) -> float:
    deltas = [combo[0]] + [
        combo[index] - combo[index - 1]
        for index in range(1, len(combo))
    ]
    within_15 = sum(1 <= delta <= 15 for delta in deltas) / len(deltas)
    uniqueness = len(set(deltas)) / len(deltas)
    repeated_penalty = max(0, max(Counter(deltas).values()) - 2) / 4
    max_delta_score = max(0.0, 1.0 - abs(max(deltas) - 11) / 18)
    range_score = max(0.0, 1.0 - abs((combo[-1] - combo[0]) - 34) / 30)
    return max(
        0.0,
        0.42 * within_15
        + 0.21 * uniqueness
        + 0.18 * max_delta_score
        + 0.19 * range_score
        - 0.20 * repeated_penalty,
    )


def _carryover_score(
    combo: tuple[int, ...], latest_numbers: set[int]
) -> float:
    overlap = len(set(combo) & latest_numbers)
    return {0: 0.38, 1: 1.0, 2: 0.88, 3: 0.35}.get(overlap, 0.0)


def _build_seen_subset_counts(
    history: list[LottoDraw],
) -> tuple[Counter[tuple[int, ...]], Counter[tuple[int, ...]]]:
    quads: Counter[tuple[int, ...]] = Counter()
    quints: Counter[tuple[int, ...]] = Counter()
    for draw in history:
        quads.update(combinations(draw.numbers, 4))
        quints.update(combinations(draw.numbers, 5))
    return quads, quints


def _score_components(
    combo: tuple[int, ...],
    number_scores: dict[int, float],
    method: MethodDefinition,
    context: dict[str, Any],
    latest_numbers: set[int],
) -> dict[str, float]:
    pair_graph: dict[tuple[int, int], float] = context["pair_graph"]
    pair_values = [
        pair_graph[tuple(sorted(pair))] for pair in combinations(combo, 2)
    ]
    return {
        "individual": fmean(number_scores[number] for number in combo),
        "pair": (fmean(pair_values) + 1.0) / 2.0,
        "diversity": _combo_diversity(combo, context["velocity"]),
        "balance": _balance_score(combo),
        "delta": _delta_score(combo),
        "carryover": _carryover_score(combo, latest_numbers),
    }


def _combo_score(
    combo: tuple[int, ...],
    number_scores: dict[int, float],
    method: MethodDefinition,
    context: dict[str, Any],
    latest_numbers: set[int],
    quads: Counter[tuple[int, ...]],
    quints: Counter[tuple[int, ...]],
) -> tuple[float, dict[str, float]]:
    components = _score_components(
        combo, number_scores, method, context, latest_numbers
    )
    latest_overlap = len(set(combo) & latest_numbers)
    repeated_quad = max(
        (quads[subset] for subset in combinations(combo, 4)), default=0
    )
    repeated_quint = max(
        (quints[subset] for subset in combinations(combo, 5)), default=0
    )

    latest_penalty_rate = 0.007 if method.carryover_weight else 0.023
    penalty = latest_penalty_rate * latest_overlap
    penalty += 0.012 * min(repeated_quad, 3)
    penalty += 0.026 * min(repeated_quint, 2)

    score = (
        0.66 * components["individual"]
        + method.pair_weight * components["pair"]
        + method.diversity_weight * components["diversity"]
        + method.balance_weight * components["balance"]
        + method.delta_weight * components["delta"]
        + method.carryover_weight * components["carryover"]
        - penalty
    )
    components["historical_similarity_penalty"] = penalty
    return score, components


def _candidate_pool(
    method: MethodDefinition, number_scores: dict[int, float]
) -> tuple[int, ...]:
    ordered = sorted(NUMBERS, key=lambda number: (-number_scores[number], number))
    base_count = max(14, method.pool_size - 10)
    selected: list[int] = ordered[:base_count]

    ranges = ((1, 9), (10, 19), (20, 29), (30, 39), (40, 45))
    for start, end in ranges:
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


def _select_candidate(
    method: MethodDefinition,
    history: list[LottoDraw],
    ranked: dict[str, dict[int, float]],
    context: dict[str, Any],
    selected: list[tuple[int, ...]],
    past_combos: set[tuple[int, ...]],
    quads: Counter[tuple[int, ...]],
    quints: Counter[tuple[int, ...]],
) -> tuple[tuple[int, ...], float, dict[str, float]]:
    number_scores = _method_number_scores(method, ranked)
    pool = _candidate_pool(method, number_scores)
    latest_numbers = set(history[-1].numbers)

    scored: list[tuple[float, tuple[int, ...], dict[str, float]]] = []
    for combo in combinations(pool, 6):
        if combo in past_combos:
            continue
        score, components = _combo_score(
            combo,
            number_scores,
            method,
            context,
            latest_numbers,
            quads,
            quints,
        )
        scored.append((score, combo, components))
    scored.sort(key=lambda item: (-item[0], item[1]))

    usage = Counter(number for previous in selected for number in previous)
    for max_overlap in (3, 4, 5):
        for score, combo, components in scored[:1200]:
            if any(usage[number] >= 3 for number in combo):
                continue
            if all(
                len(set(combo) & set(previous)) <= max_overlap
                for previous in selected
            ):
                return combo, score, components
    if not scored:
        raise ValueError("추천 가능한 조합을 생성하지 못했습니다")
    return scored[0][1], scored[0][0], scored[0][2]


def _max_past_overlap(
    combo: tuple[int, ...], history: Iterable[LottoDraw]
) -> int:
    values = set(combo)
    return max(
        (len(values & set(draw.numbers)) for draw in history), default=0
    )


def _strongest_pair(
    combo: tuple[int, ...], context: dict[str, Any]
) -> tuple[tuple[int, int], float]:
    pair_graph: dict[tuple[int, int], float] = context["pair_graph"]
    return max(
        (
            (tuple(sorted(pair)), pair_graph[tuple(sorted(pair))])
            for pair in combinations(combo, 2)
        ),
        key=lambda item: (item[1], tuple(-number for number in item[0])),
    )


def _recommendation_reason(
    method: MethodDefinition,
    combo: tuple[int, ...],
    context: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    velocity: dict[int, float] = context["velocity"]
    transition: dict[int, float] = context["transition_raw"]
    gap: dict[int, int] = context["gap"]
    phase_leaders = sorted(combo, key=lambda n: (-abs(velocity[n]), n))[:2]
    transition_leaders = sorted(combo, key=lambda n: (-transition[n], n))[:2]
    overdue_leaders = sorted(combo, key=lambda n: (-gap[n], n))[:2]
    pair, pair_value = _strongest_pair(combo, context)

    reasons = {
        METHOD_PHASE_RESIDUAL: (
            f"장·단기 잔차 방향 변화가 큰 {phase_leaders[0]}·{phase_leaders[1]}, "
            f"전이 상위 {transition_leaders[0]}, 강한 연결 {pair[0]}-{pair[1]} 반영"
        ),
        METHOD_TRANSITION_GAP: (
            f"다음 회차 전이 상위 {transition_leaders[0]}·{transition_leaders[1]}와 "
            f"미출현 간격·시간축 곡률, {pair[0]}-{pair[1]} 연결을 결합"
        ),
        METHOD_WEIGHTED_FREQUENCY: (
            f"최근 10·30·100회 및 전체 빈도를 가중 합산하고 "
            f"{pair[0]}-{pair[1]} 동반출현과 구간 균형을 보정"
        ),
        METHOD_HOT_NUMBERS: (
            f"최근 출현 상승세가 큰 {phase_leaders[0]}·{phase_leaders[1]}를 중심으로 "
            f"핫넘버 집중과 번호대 쏠림을 함께 제어"
        ),
        METHOD_OVERDUE_GAP: (
            f"현재 미출현 간격이 긴 {overdue_leaders[0]}·{overdue_leaders[1]}를 포함하되 "
            f"콜드넘버 과집중과 장기 극단값을 제한"
        ),
        METHOD_PAIR_COOCCURRENCE: (
            f"전체+최근 120회 동반출현 그래프 중심 조합이며 "
            f"가장 강한 내부 연결은 {pair[0]}-{pair[1]}"
        ),
        METHOD_BALANCE: (
            f"번호합 {sum(combo)}, 홀수 {sum(n % 2 for n in combo)}개, "
            f"저구간 {sum(n <= 22 for n in combo)}개와 번호대 분산을 균형화"
        ),
        METHOD_DELTA: (
            "오름차순 번호 간 델타의 크기·반복·전체 범위를 공개 델타 규칙으로 "
            f"평가하고 {pair[0]}-{pair[1]} 연결을 보조 반영"
        ),
        METHOD_CARRYOVER: (
            f"직전 회차와 {len(set(combo) & set(context['latest_numbers']))}개 이월을 "
            f"허용하고 전이 상위 {transition_leaders[0]}·{transition_leaders[1]}를 결합"
        ),
        METHOD_PUBLIC_ENSEMBLE: (
            f"가중 빈도·미출현·동반출현·균형·델타·이월수의 합의 점수를 적용; "
            f"핵심 연결 {pair[0]}-{pair[1]}, 번호합 {sum(combo)}"
        ),
    }
    details = {
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
        "carryover_count": len(
            set(combo) & set(context["latest_numbers"])
        ),
    }
    return reasons[method.method_id], details


def build_analysis(
    history: list[LottoDraw],
    method_ids: Sequence[str] | None = None,
) -> AnalysisResult:
    """Build one deterministic recommendation for every selected method."""
    if len(history) < 30:
        raise ValueError("분석에는 최소 30개 회차가 필요합니다")
    history = sorted(history, key=lambda draw: draw.round)
    expected_rounds = list(range(history[0].round, history[-1].round + 1))
    actual_rounds = [draw.round for draw in history]
    if history[0].round != 1 or actual_rounds != expected_rounds:
        raise ValueError("1회부터 최신 회차까지 연속된 전체 데이터가 필요합니다")

    selected_method_ids = normalize_method_ids(
        method_ids if method_ids is not None else DEFAULT_METHOD_IDS
    )
    ranked, context = _feature_maps(history)
    context["latest_numbers"] = list(history[-1].numbers)
    past_combos = {tuple(draw.numbers) for draw in history}
    quads, quints = _build_seen_subset_counts(history)

    selected: list[tuple[int, ...]] = []
    recommendations: list[Recommendation] = []
    for index, method_id in enumerate(selected_method_ids, start=1):
        method = METHODS_BY_ID[method_id]
        combo, score, components = _select_candidate(
            method,
            history,
            ranked,
            context,
            selected,
            past_combos,
            quads,
            quints,
        )
        selected.append(combo)
        reason, details = _recommendation_reason(method, combo, context)
        details.update(
            {
                "score_components": {
                    key: round(value, 4)
                    for key, value in components.items()
                },
                "exact_past_first_prize_match": False,
                "max_numbers_matching_any_past_first_prize": _max_past_overlap(
                    combo, history
                ),
                "latest_draw_overlap": len(
                    set(combo) & set(history[-1].numbers)
                ),
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

    transition = context["transition_raw"]
    velocity = context["velocity"]
    graph_strength = context["graph_strength_raw"]
    summary = {
        "algorithm": "selectable_multi_formula_v2",
        "history_draws": len(history),
        "selected_method_ids": list(selected_method_ids),
        "selected_methods": [
            {
                "method_id": method_id,
                "label": METHODS_BY_ID[method_id].label,
                "category": METHODS_BY_ID[method_id].category,
                "description": METHODS_BY_ID[method_id].description,
            }
            for method_id in selected_method_ids
        ],
        "top_phase_change": sorted(
            NUMBERS, key=lambda n: (-abs(velocity[n]), n)
        )[:6],
        "top_transition": sorted(
            NUMBERS, key=lambda n: (-transition[n], n)
        )[:6],
        "top_graph_strength": sorted(
            NUMBERS, key=lambda n: (-graph_strength[n], n)
        )[:6],
        "first_prize_odds": FIRST_PRIZE_ODDS,
        "public_formula_notice": PUBLIC_FORMULA_NOTICE,
        "disclaimer": DISCLAIMER,
    }
    return AnalysisResult(
        target_round=history[-1].round + 1,
        based_on_round=history[-1].round,
        recommendations=tuple(recommendations),
        summary=summary,
    )
