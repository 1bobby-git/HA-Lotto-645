"""Pure-Python validation tests for the shared Lotto history mirror."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_PATH = ROOT / "custom_components" / "lotto_645"

custom_components = sys.modules.setdefault(
    "custom_components", types.ModuleType("custom_components")
)
custom_components.__path__ = [str(ROOT / "custom_components")]
package = sys.modules.setdefault(
    "custom_components.lotto_645", types.ModuleType("custom_components.lotto_645")
)
package.__path__ = [str(PACKAGE_PATH)]


def _load(name: str) -> types.ModuleType:
    full_name = f"custom_components.lotto_645.{name}"
    if full_name in sys.modules:
        return sys.modules[full_name]
    spec = importlib.util.spec_from_file_location(full_name, PACKAGE_PATH / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


models = _load("models")
history = _load("history")
const = _load("const")


def test_bundled_history_is_complete_and_hash_verified():
    draws, metadata = history.load_bundled_history()
    assert len(draws) >= 1240
    assert draws[0].round == 1
    assert draws[-1].round == metadata["latest_round"]
    assert [draw.round for draw in draws] == list(range(1, draws[-1].round + 1))
    assert metadata["draws_sha256"]


def test_known_round_1240_is_preserved():
    draws, _ = history.load_bundled_history()
    draw = draws[1239]
    assert draw.round == 1240
    assert draw.numbers == (11, 13, 19, 20, 31, 44)
    assert draw.bonus == 27


def test_official_direct_fallback_is_opt_in():
    assert const.DEFAULT_ALLOW_OFFICIAL_FALLBACK is False
    assert const.OFFICIAL_DIRECT_MAX_MISSING_ROUNDS <= 2
    assert const.OFFICIAL_MAX_REQUESTS_PER_UPDATE <= 4
    assert const.OFFICIAL_MIN_INTERVAL_SECONDS >= 3.0
