"""Pure-Python regression tests for the deterministic analysis engine."""

from __future__ import annotations

from datetime import date
import importlib.util
from pathlib import Path
import random
import sys
import types

import pytest

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


def _profile():
    return {
        "calendar": "solar",
        "birth_date": "1990-05-17",
        "birth_time": "14:30",
        "lunar_leap_month": False,
        "gender": "male",
        "birth_place": "Seoul",
        "timezone": "Asia/Seoul",
        "true_solar_time": False,
        "longitude": None,
    }


def test_catalog_and_default_gating():
    assert len(methods.METHODS) == 17
    assert len(methods.PUBLIC_METHOD_IDS) == 12
    assert methods.METHOD_MYUNGRI_HETU not in methods.DEFAULT_METHOD_IDS
    myungri_method = methods.METHODS_BY_ID[methods.METHOD_MYUNGRI_HETU]
    assert "개인 사주" in myungri_method.description


def test_personal_saju_profile_builds_four_pillars():
    profile = _profile()
    myungri.validate_saju_profile(profile)
    context = myungri.build_myungri_context("2026-09-05", profile)
    assert context["status"] == "ready"
    assert set(context["natal_pillars"]) == {"year", "month", "day", "time"}
    assert context["day_master"]
    assert context["strength"] in {"신강", "신약", "중화"}
    assert context["favorable_elements_ko"]
    assert context["target_pillars"]["day"]["ganzhi"]
    assert context["luck_cycle"]


def test_myungri_requires_profile():
    with pytest.raises(ValueError, match="개인 사주정보"):
        analysis.build_analysis(_history(), (methods.METHOD_MYUNGRI_HETU,))


def test_personal_myungri_recommendation_details():
    history = _history()
    selected = (methods.METHOD_PHASE_RESIDUAL, methods.METHOD_MYUNGRI_HETU)
    result = analysis.build_analysis(history, selected, 0, _profile())
    traditional = result.recommendation_by_method(methods.METHOD_MYUNGRI_HETU)
    assert traditional is not None
    assert traditional.details["saju_profile_status"] == "준비됨"
    assert len(traditional.details["four_pillars"]) == 4
    assert traditional.details["day_master_strength"] in {"신강", "신약", "중화"}
    assert traditional.details["current_daewoon"]
    assert traditional.details["target_interactions"] is not None
    assert traditional.numbers not in {draw.numbers for draw in history}


def test_every_non_saju_method_runs_individually_without_birth_profile():
    """Selecting any ordinary method must never depend on Saju input."""
    history = _history(120)
    past = {draw.numbers for draw in history}
    for method in methods.METHODS:
        if method.method_id in {methods.METHOD_MYUNGRI_HETU, methods.METHOD_SELECTED_MEDIAN}:
            continue
        result = analysis.build_analysis(history, (method.method_id,), 0)
        assert len(result.recommendations) == 1, method.method_id
        recommendation = result.recommendations[0]
        assert recommendation.method_id == method.method_id
        assert recommendation.numbers not in past
        assert len(set(recommendation.numbers)) == 6


def test_all_selectable_methods_run_together_with_valid_saju_profile():
    """Catch KeyError/missing-feature regressions from newly selectable methods."""
    history = _history(120)
    selected = tuple(method.method_id for method in methods.METHODS)
    result = analysis.build_analysis(history, selected, 0, _profile())
    assert [item.method_id for item in result.recommendations] == list(selected)
    assert len(result.recommendations) == len(methods.METHODS)
    assert len({item.numbers for item in result.recommendations}) == len(
        result.recommendations
    )


def test_manual_generation_nonce_rotates_local_candidates():
    history = _history(120)
    selected = (
        methods.METHOD_PHASE_RESIDUAL,
        methods.METHOD_WEIGHTED_FREQUENCY,
        methods.METHOD_PUBLIC_ENSEMBLE,
    )
    baseline = analysis.build_analysis(history, selected, 0)
    regenerated = analysis.build_analysis(history, selected, 1)
    assert [item.numbers for item in baseline.recommendations] != [
        item.numbers for item in regenerated.recommendations
    ]



def test_selected_median_requires_two_other_methods():
    history = _history(120)
    with pytest.raises(ValueError, match="2개 이상"):
        analysis.build_analysis(
            history,
            (methods.METHOD_WEIGHTED_FREQUENCY, methods.METHOD_SELECTED_MEDIAN),
        )


def test_selected_median_uses_only_selected_local_methods_and_runs_last():
    history = _history(120)
    selected = (
        methods.METHOD_PHASE_RESIDUAL,
        methods.METHOD_WEIGHTED_FREQUENCY,
        methods.METHOD_PAIR_COOCCURRENCE,
        methods.METHOD_SELECTED_MEDIAN,
    )
    result = analysis.build_analysis(history, selected, 0)
    assert len(result.recommendations) == 4
    consensus = result.recommendations[-1]
    assert consensus.method_id == methods.METHOD_SELECTED_MEDIAN
    assert consensus.details["consensus_source_count"] == 3
    assert consensus.details["consensus_source_method_ids"] == list(selected[:-1])
    assert consensus.details["consensus_rule"].startswith("선택한 다른 로컬 방식")
    assert set(consensus.details["consensus_number_median_scores"]) == {
        str(number) for number in consensus.numbers
    }
    assert all(
        0 <= value <= 3
        for value in consensus.details["consensus_number_support_votes"].values()
    )
    assert consensus.numbers not in {draw.numbers for draw in history}
    assert result.summary["execution_method_ids"][-1] == methods.METHOD_SELECTED_MEDIAN
