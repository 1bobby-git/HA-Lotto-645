"""Deterministic Lotto 6/45 heuristic analysis engine.

This module intentionally avoids claiming predictive power. It converts historical
results into several residual, transition, and graph features, then chooses five
diverse combinations that have never exactly won before.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from itertools import combinations
import math
from statistics import fmean
from typing import Any

from .const import DISCLAIMER, FIRST_PRIZE_ODDS
from .models import AnalysisResult, LottoDraw, Recommendation

NUMBERS = tuple(range(1, 46))
DRAW_SIZE = 6
NUMBER_PROBABILITY = DRAW_SIZE / 45
PAIR_PROBABILITY = (6 / 45) * (5 / 44)


@dataclass(frozen=True, slots=True)
class Profile:
    label: str
    method: str
    weights: dict[str, float]
    pair_weight: float
    diversity_weight: float


PROFILES = (
    Profile(
        "독창 패턴 ①",
        "위상-잔차 그래프",
        {
            "counter_phase": 0.34,
            "phase_velocity": 0.23,
            "transition": 0.20,
            "curvature": 0.13,
            "gap_surprise": 0.10,
        },
        pair_weight=0.20,
        diversity_weight=0.10,
    ),
    Profile(
        "독창 패턴 ②",
        "전이-간격 위상",
        {
            "transition": 0.31,
            "curvature": 0.24,
            "gap_surprise": 0.18,
            "counter_phase": 0.17,
            "long_neutral": 0.10,
        },
        pair_weight=0.17,
        diversity_weight=0.12,
    ),
    Profile(
        "공식 탐색 ①",
        "구조 수렴 휴리스틱",
        {
            "transition": 0.29,
            "graph_strength": 0.26,
            "counter_phase": 0.18,
            "gap_balance": 0.15,
            "recent_neutral": 0.12,
        },
        pair_weight=0.21,
        diversity_weight=0.08,
    ),
    Profile(
        "공식 탐색 ②",
        "쌍 그래프 결속",
        {
            "graph_strength": 0.38,
            "transition": 0.22,
            "phase_velocity": 0.18,
            "gap_balance": 0.12,
            "long_neutral": 0.10,
        },
        pair_weight=0.28,
        diversity_weight=0.05,
    ),
    Profile(
        "공식 탐색 ③",
        "시간축 균형 휴리스틱",
        {
            "long_neutral": 0.24,
            "recent_neutral": 0.23,
            "transition": 0.20,
            "graph_strength": 0.18,
            "gap_balance": 0.15,
        },
        pair_weight=0.16,
        diversity_weight=0.14,
    ),
)


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
    return {number: index / (len(ordered) - 1) for index, number in enumerate(ordered)}


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


def _feature_maps(history: list[LottoDraw]) -> tuple[dict[str, dict[int, float]], dict[str, Any]]:
    n = len(history)
    count_long = _count_window(history, n)
    count_30 = _count_window(history, 30)
    count_120 = _count_window(history, 120)
    count_260 = _count_window(history, 260)

    n30 = min(30, n)
    n120 = min(120, n)
    n260 = min(260, n)

    z_long = {number: _z_residual(count_long[number], n, NUMBER_PROBABILITY) for number in NUMBERS}
    z30 = {number: _z_residual(count_30[number], n30, NUMBER_PROBABILITY) for number in NUMBERS}
    z120 = {number: _z_residual(count_120[number], n120, NUMBER_PROBABILITY) for number in NUMBERS}
    z260 = {number: _z_residual(count_260[number], n260, NUMBER_PROBABILITY) for number in NUMBERS}

    velocity = {number: z30[number] - z120[number] for number in NUMBERS}
    curvature = {
        number: abs((z30[number] - z120[number]) - (z120[number] - z260[number]))
        for number in NUMBERS
    }
    counter_phase = {
        number: max(0.0, -(z_long[number] * velocity[number]))
        for number in NUMBERS
    }

    expected_gap = (1.0 - NUMBER_PROBABILITY) / NUMBER_PROBABILITY
    gap_sd = math.sqrt((1.0 - NUMBER_PROBABILITY) / (NUMBER_PROBABILITY**2))
    raw_gap = {number: _gap_since_last(history, number) for number in NUMBERS}
    gap_z = {number: (raw_gap[number] - expected_gap) / gap_sd for number in NUMBERS}
    gap_surprise = {number: min(abs(gap_z[number]), 2.5) for number in NUMBERS}
    gap_balance = {number: -abs(gap_z[number]) for number in NUMBERS}

    transition = _transition_scores(history)
    pair_graph, graph_strength = _pair_graph(history)

    raw_features = {
        "counter_phase": counter_phase,
        "phase_velocity": {number: abs(velocity[number]) for number in NUMBERS},
        "transition": transition,
        "curvature": curvature,
        "gap_surprise": gap_surprise,
        "gap_balance": gap_balance,
        "graph_strength": graph_strength,
        "long_neutral": {number: -abs(z_long[number]) for number in NUMBERS},
        "recent_neutral": {number: -abs(z30[number]) for number in NUMBERS},
    }
    ranked = {name: _rank01(values) for name, values in raw_features.items()}
    context = {
        "z_long": z_long,
        "z30": z30,
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


def _profile_number_scores(
    profile: Profile, ranked: dict[str, dict[int, float]]
) -> dict[int, float]:
    result: dict[int, float] = {}
    for number in NUMBERS:
        result[number] = sum(
            weight * ranked[name][number] for name, weight in profile.weights.items()
        )
    return result


def _combo_diversity(combo: tuple[int, ...], velocity: dict[int, float]) -> float:
    signs = [1.0 if velocity[number] >= 0 else -1.0 for number in combo]
    phase_mix = 1.0 - abs(fmean(signs))
    gaps = [combo[index + 1] - combo[index] for index in range(len(combo) - 1)]
    mean_gap = fmean(gaps)
    spread = math.sqrt(fmean((gap - mean_gap) ** 2 for gap in gaps))
    spacing_mix = min(spread / 7.0, 1.0)
    return 0.62 * phase_mix + 0.38 * spacing_mix


def _build_seen_subset_counts(history: list[LottoDraw]) -> tuple[Counter[tuple[int, ...]], Counter[tuple[int, ...]]]:
    quads: Counter[tuple[int, ...]] = Counter()
    quints: Counter[tuple[int, ...]] = Counter()
    for draw in history:
        quads.update(combinations(draw.numbers, 4))
        quints.update(combinations(draw.numbers, 5))
    return quads, quints


def _combo_score(
    combo: tuple[int, ...],
    number_scores: dict[int, float],
    profile: Profile,
    context: dict[str, Any],
    latest_numbers: set[int],
    quads: Counter[tuple[int, ...]],
    quints: Counter[tuple[int, ...]],
) -> float:
    individual = fmean(number_scores[number] for number in combo)
    pair_graph: dict[tuple[int, int], float] = context["pair_graph"]
    pair_values = [pair_graph[tuple(sorted(pair))] for pair in combinations(combo, 2)]
    pair_score = (fmean(pair_values) + 1.0) / 2.0
    diversity = _combo_diversity(combo, context["velocity"])

    latest_overlap = len(set(combo) & latest_numbers)
    repeated_quad = max((quads[sub] for sub in combinations(combo, 4)), default=0)
    repeated_quint = max((quints[sub] for sub in combinations(combo, 5)), default=0)

    penalty = 0.026 * latest_overlap
    penalty += 0.012 * min(repeated_quad, 3)
    penalty += 0.026 * min(repeated_quint, 2)

    return (
        0.70 * individual
        + profile.pair_weight * pair_score
        + profile.diversity_weight * diversity
        - penalty
    )


def _select_candidate(
    profile: Profile,
    history: list[LottoDraw],
    ranked: dict[str, dict[int, float]],
    context: dict[str, Any],
    selected: list[tuple[int, ...]],
    past_combos: set[tuple[int, ...]],
    quads: Counter[tuple[int, ...]],
    quints: Counter[tuple[int, ...]],
) -> tuple[tuple[int, ...], float]:
    number_scores = _profile_number_scores(profile, ranked)
    pool = sorted(NUMBERS, key=lambda n: (-number_scores[n], n))[:22]
    latest_numbers = set(history[-1].numbers)

    scored: list[tuple[float, tuple[int, ...]]] = []
    for combo in combinations(sorted(pool), 6):
        if combo in past_combos:
            continue
        score = _combo_score(
            combo, number_scores, profile, context, latest_numbers, quads, quints
        )
        scored.append((score, combo))
    scored.sort(key=lambda item: (-item[0], item[1]))

    usage = Counter(number for previous in selected for number in previous)
    for max_overlap in (3, 4, 5):
        for score, combo in scored[:800]:
            if any(usage[number] >= 3 for number in combo):
                continue
            if all(len(set(combo) & set(previous)) <= max_overlap for previous in selected):
                return combo, score
    if not scored:
        raise ValueError("추천 가능한 조합을 생성하지 못했습니다")
    return scored[0][1], scored[0][0]


def _max_past_overlap(combo: tuple[int, ...], history: Iterable[LottoDraw]) -> int:
    values = set(combo)
    return max((len(values & set(draw.numbers)) for draw in history), default=0)


def _recommendation_reason(
    profile: Profile, combo: tuple[int, ...], context: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    velocity: dict[int, float] = context["velocity"]
    transition: dict[int, float] = context["transition_raw"]
    pair_graph: dict[tuple[int, int], float] = context["pair_graph"]
    gap: dict[int, int] = context["gap"]

    phase_leaders = sorted(combo, key=lambda n: (-abs(velocity[n]), n))[:2]
    transition_leaders = sorted(combo, key=lambda n: (-transition[n], n))[:2]
    pair, pair_value = max(
        ((tuple(sorted(pair)), pair_graph[tuple(sorted(pair))]) for pair in combinations(combo, 2)),
        key=lambda item: (item[1], tuple(-n for n in item[0])),
    )

    if profile.method == "위상-잔차 그래프":
        reason = (
            f"장·단기 잔차의 방향 변화가 큰 {phase_leaders[0]}·{phase_leaders[1]}, "
            f"다음 회차 전이 점수가 높은 {transition_leaders[0]}, "
            f"쌍 그래프 결속이 강한 {pair[0]}-{pair[1]}를 함께 반영"
        )
    elif profile.method == "전이-간격 위상":
        reason = (
            f"최근 시간축 곡률과 미출현 간격 위상, 다음 회차 전이를 결합; "
            f"전이 상위 {transition_leaders[0]}·{transition_leaders[1]}, "
            f"핵심 연결 {pair[0]}-{pair[1]}"
        )
    elif profile.method == "구조 수렴 휴리스틱":
        reason = (
            f"전이·쌍 그래프·간격 균형이 동시에 수렴하는 수를 우선; "
            f"{transition_leaders[0]}·{transition_leaders[1]} 전이와 "
            f"{pair[0]}-{pair[1]} 연결이 핵심"
        )
    elif profile.method == "쌍 그래프 결속":
        reason = (
            f"역대+최근 120회 쌍 동시출현 잔차를 결합한 그래프 중심 조합; "
            f"가장 강한 내부 연결은 {pair[0]}-{pair[1]}"
        )
    else:
        reason = (
            f"장기·최근 잔차의 과도한 극단을 줄이고 전이·그래프 균형을 우선; "
            f"핵심 전이 {transition_leaders[0]}·{transition_leaders[1]}"
        )

    details = {
        "phase_leaders": phase_leaders,
        "transition_leaders": transition_leaders,
        "strongest_pair": list(pair),
        "strongest_pair_score": round(pair_value, 4),
        "gaps_since_last": {str(number): gap[number] for number in combo},
    }
    return reason, details


def build_analysis(history: list[LottoDraw]) -> AnalysisResult:
    """Build five deterministic recommendations from complete historical data."""
    if len(history) < 30:
        raise ValueError("분석에는 최소 30개 회차가 필요합니다")
    history = sorted(history, key=lambda draw: draw.round)
    expected_rounds = list(range(history[0].round, history[-1].round + 1))
    actual_rounds = [draw.round for draw in history]
    if history[0].round != 1 or actual_rounds != expected_rounds:
        raise ValueError("1회부터 최신 회차까지 연속된 전체 데이터가 필요합니다")

    ranked, context = _feature_maps(history)
    past_combos = {tuple(draw.numbers) for draw in history}
    quads, quints = _build_seen_subset_counts(history)

    selected: list[tuple[int, ...]] = []
    recommendations: list[Recommendation] = []
    for index, profile in enumerate(PROFILES, start=1):
        combo, score = _select_candidate(
            profile,
            history,
            ranked,
            context,
            selected,
            past_combos,
            quads,
            quints,
        )
        selected.append(combo)
        reason, details = _recommendation_reason(profile, combo, context)
        details.update(
            {
                "exact_past_first_prize_match": False,
                "max_numbers_matching_any_past_first_prize": _max_past_overlap(combo, history),
                "latest_draw_overlap": len(set(combo) & set(history[-1].numbers)),
            }
        )
        recommendations.append(
            Recommendation(
                index=index,
                label=profile.label,
                method=profile.method,
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
        "algorithm": "phase_residual_graph_v1",
        "history_draws": len(history),
        "top_phase_change": sorted(NUMBERS, key=lambda n: (-abs(velocity[n]), n))[:6],
        "top_transition": sorted(NUMBERS, key=lambda n: (-transition[n], n))[:6],
        "top_graph_strength": sorted(NUMBERS, key=lambda n: (-graph_strength[n], n))[:6],
        "first_prize_odds": FIRST_PRIZE_ODDS,
        "disclaimer": DISCLAIMER,
    }
    return AnalysisResult(
        target_round=history[-1].round + 1,
        based_on_round=history[-1].round,
        recommendations=tuple(recommendations),
        summary=summary,
    )
