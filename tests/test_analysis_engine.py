"""Pure-Python regression tests for the deterministic analysis engine."""

from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
import random
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = ROOT / "custom_components" / "lotto_645"

custom_components = types.ModuleType("custom_components")
custom_components.__path__ = [str(ROOT / "custom_components")]
sys.modules.setdefault("custom_components", custom_components)
package = types.ModuleType("custom_components.lotto_645")
package.__path__ = [str(PACKAGE_PATH)]
sys.modules.setdefault("custom_components.lotto_645", package)


def _load(name: str) -> types.ModuleType:
    full_name = f"custom_components.lotto_645.{name}"
    spec = importlib.util.spec_from_file_location(full_name, PACKAGE_PATH / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


const = _load("const")
models = _load("models")
methods = _load("methods")
myungri = _load("myungri")
analysis = _load("analysis")


def _history(count: int = 180):
    rng = random.Random(645)
    rows = []
    start = date(2022, 1, 1)
    for round_no in range(1, count + 1):
        numbers = tuple(sorted(rng.sample(range(1, 46), 6)))
        remaining = [number for number in range(1, 46) if number not in numbers]
        draw_date = start.fromordinal(start.toordinal() + (round_no - 1) * 7)
        rows.append(
            models.LottoDraw(
                round=round_no,
                draw_date=draw_date.isoformat(),
                numbers=numbers,
                bonus=rng.choice(remaining),
            )
        )
    return rows


def test_catalog_exposes_expanded_methods_without_numbered_names():
    assert len(methods.METHODS) == 16
    assert len(methods.PUBLIC_METHOD_IDS) == 12
    assert len(methods.TRADITIONAL_METHOD_IDS) == 1
    assert methods.METHOD_PUBLIC_ENSEMBLE in methods.DEFAULT_METHOD_IDS
    assert methods.METHOD_MYUNGRI_HETU in methods.DEFAULT_METHOD_IDS
    assert len(set(methods.DEFAULT_METHOD_IDS)) == len(methods.DEFAULT_METHOD_IDS)
    for method in methods.METHODS:
        assert "①" not in method.label
        assert "②" not in method.label
        assert "③" not in method.label
        assert method.description and len(method.description) >= 25


def test_sexagenary_anchor_and_hetu_mapping():
    anchor = myungri.sexagenary_day(date(1949, 10, 1))
    assert anchor["name"] == "갑자(甲子)"
    assert anchor["cycle_position"] == 1
    assert myungri.number_element(1) == "water"
    assert myungri.number_element(6) == "water"
    assert myungri.number_element(2) == "fire"
    assert myungri.number_element(7) == "fire"
    assert myungri.number_element(3) == "wood"
    assert myungri.number_element(8) == "wood"
    assert myungri.number_element(4) == "metal"
    assert myungri.number_element(9) == "metal"
    assert myungri.number_element(5) == "earth"
    assert myungri.number_element(10) == "earth"


def test_selected_methods_keep_order_and_exclude_past_exact_winners():
    history = _history()
    selected = (
        methods.METHOD_PHASE_RESIDUAL,
        methods.METHOD_RECENCY_DECAY,
        methods.METHOD_TRIPLET_COOCCURRENCE,
        methods.METHOD_PUBLIC_ENSEMBLE,
        methods.METHOD_MYUNGRI_HETU,
    )
    result = analysis.build_analysis(history, selected)
    assert [item.method_id for item in result.recommendations] == list(selected)
    assert result.target_round == history[-1].round + 1
    past = {draw.numbers for draw in history}
    for recommendation in result.recommendations:
        assert len(recommendation.numbers) == 6
        assert len(set(recommendation.numbers)) == 6
        assert all(1 <= number <= 45 for number in recommendation.numbers)
        assert recommendation.numbers not in past
        assert recommendation.details["exact_past_first_prize_match"] is False
        assert recommendation.details["method_description"]

    traditional = result.recommendation_by_method(methods.METHOD_MYUNGRI_HETU)
    assert traditional is not None
    assert traditional.details["traditional_method"].startswith("60갑자")
    assert traditional.details["target_draw_date"]
    assert traditional.details["sexagenary_day"]
    assert traditional.details["day_master_element"] in {"목", "화", "토", "금", "수"}
    assert sum(traditional.details["five_element_counts"].values()) == 6


def test_same_history_options_and_nonce_are_deterministic():
    history = _history(120)
    selected = (
        methods.METHOD_TRANSITION_GAP,
        methods.METHOD_BAYESIAN_SHRINKAGE,
        methods.METHOD_CYCLE_RHYTHM,
    )
    first = analysis.build_analysis(history, selected, 4)
    second = analysis.build_analysis(history, selected, 4)
    assert [item.numbers for item in first.recommendations] == [
        item.numbers for item in second.recommendations
    ]
    assert first.summary["generation_sequence"] == 4


def test_manual_generation_nonce_rotates_local_candidates():
    history = _history(120)
    selected = (
        methods.METHOD_PHASE_RESIDUAL,
        methods.METHOD_WEIGHTED_FREQUENCY,
        methods.METHOD_PUBLIC_ENSEMBLE,
    )
    baseline = analysis.build_analysis(history, selected, 0)
    regenerated = analysis.build_analysis(history, selected, 1)
    again = analysis.build_analysis(history, selected, 2)
    baseline_numbers = [item.numbers for item in baseline.recommendations]
    regenerated_numbers = [item.numbers for item in regenerated.recommendations]
    again_numbers = [item.numbers for item in again.recommendations]
    assert regenerated_numbers != baseline_numbers
    assert again_numbers != regenerated_numbers
    past = {draw.numbers for draw in history}
    for result in (regenerated, again):
        for item in result.recommendations:
            assert item.numbers not in past
