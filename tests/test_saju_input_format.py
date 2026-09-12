"""Compact Saju input normalization tests."""

from pathlib import Path
import importlib
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
for name, path in (
    ("custom_components", ROOT / "custom_components"),
    ("custom_components.lotto_645", ROOT / "custom_components" / "lotto_645"),
):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules.setdefault(name, module)

calendar = importlib.import_module("custom_components.lotto_645.saju_calendar")


def test_compact_birth_date_is_normalized_and_parsed():
    assert calendar.normalize_birth_date("19820311") == "1982-03-11"
    assert calendar.date_parts("19820311") == (1982, 3, 11)
    assert calendar.date_parts("1982-03-11") == (1982, 3, 11)


def test_compact_birth_time_is_normalized_and_parsed():
    assert calendar.normalize_birth_time("1625") == "16:25"
    assert calendar.birth_clock("1625") == (16, 25)
    assert calendar.birth_clock("16:25") == (16, 25)


def test_unknown_birth_time_still_works():
    assert calendar.normalize_birth_time("미상") == "미상"
    assert calendar.birth_clock("미상") is None


@pytest.mark.parametrize("value", ["1982031", "198203111", "1982/03/11"])
def test_ambiguous_date_shapes_are_not_silently_rewritten(value):
    assert calendar.normalize_birth_date(value) == value
    with pytest.raises(calendar.SajuProfileError):
        calendar.date_parts(value)


@pytest.mark.parametrize("value", ["625", "16255", "16.25"])
def test_ambiguous_time_shapes_are_not_silently_rewritten(value):
    assert calendar.normalize_birth_time(value) == value
    with pytest.raises(calendar.SajuProfileError):
        calendar.birth_clock(value)


def test_invalid_compact_values_still_fail_range_checks():
    with pytest.raises(calendar.SajuProfileError):
        calendar.date_parts("19821311")
    with pytest.raises(calendar.SajuProfileError):
        calendar.birth_clock("2460")
