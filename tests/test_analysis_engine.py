"""Pure-Python regression tests for the deterministic analysis engine."""

from __future__ import annotations

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
    spec = importlib.util.spec_from_file_location(
        full_name, PACKAGE_PATH / f"{name}.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


const = _load("const")
models = _load("models")
methods = _load("methods")
analysis = _load("analysis")


def _history(count: int = 180):
    rng = random.Random(645)
    rows = []
    for round_no in range(1, count + 1):
        numbers = tuple(sorted(rng.sample(range(1, 46), 6)))
        remaining = [number for number in range(1, 46) if number not in numbers]
        rows.append(
            models.LottoDraw(
                round=round_no,
                draw_date=f"2026-01-{((round_no - 1) % 28) + 1:02d}",
                numbers=numbers,
                bonus=rng.choice(remaining),
            )
        )
    return rows


def test_catalog_exposes_original_and_public_methods():
    assert len(methods.METHODS) == 10
    assert len(methods.PUBLIC_METHOD_IDS) == 8
    assert methods.METHOD_PUBLIC_ENSEMBLE in methods.DEFAULT_METHOD_IDS
    assert len(set(methods.DEFAULT_METHOD_IDS)) == len(methods.DEFAULT_METHOD_IDS)


def test_selected_methods_keep_order_and_exclude_past_exact_winners():
    history = _history()
    selected = (
        methods.METHOD_PHASE_RESIDUAL,
        methods.METHOD_WEIGHTED_FREQUENCY,
        methods.METHOD_PUBLIC_ENSEMBLE,
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


def test_same_history_and_options_are_deterministic():
    history = _history(120)
    selected = (
        methods.METHOD_TRANSITION_GAP,
        methods.METHOD_PAIR_COOCCURRENCE,
    )
    first = analysis.build_analysis(history, selected)
    second = analysis.build_analysis(history, selected)
    assert [item.numbers for item in first.recommendations] == [
        item.numbers for item in second.recommendations
    ]
    assert [item.reason for item in first.recommendations] == [
        item.reason for item in second.recommendations
    ]
