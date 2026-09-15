"""Research extension remains additive and keeps legacy defaults unchanged."""
from pathlib import Path
import importlib
import random
import sys
import types

PACKAGE = "_lotto_research_extension_tests"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(Path(__file__).resolve().parents[1] / "custom_components/lotto_645")]
sys.modules[PACKAGE] = package

methods = importlib.import_module(PACKAGE + ".methods")
sampling = importlib.import_module(PACKAGE + ".sampling")
extension = importlib.import_module(PACKAGE + ".research_extension")


def test_install_is_additive_idempotent_and_defaults_stay_uniform():
    before = tuple(item.method_id for item in methods.METHODS)
    extension.install_research_extensions()
    after = tuple(item.method_id for item in methods.METHODS)
    extension.install_research_extensions()
    assert tuple(item.method_id for item in methods.METHODS) == after
    assert len(after) == len(before) + 2
    assert methods.DEFAULT_METHOD_IDS == ("uniform_fisher_yates",)
    assert "crowd_pattern_avoidance" in methods.METHODS_BY_ID
    assert "portfolio_triplet_coverage" in methods.METHODS_BY_ID
    assert after[-1] == methods.METHOD_SELECTED_MEDIAN


def test_research_sampling_is_valid_reproducible_and_strictly_excludes():
    extension.install_research_extensions()
    history = [(1, 2, 3, 4, 5, 6), (7, 8, 9, 10, 11, 12)]
    blocked = {(13, 14, 15, 16, 17, 18)}
    for formula in ("crowd_pattern_avoidance", "portfolio_triplet_coverage"):
        first = sampling.generate_ticket(
            formula, history=history, excluded_combinations=blocked, rng=random.Random(42)
        )
        second = sampling.generate_ticket(
            formula, history=history, excluded_combinations=blocked, rng=random.Random(42)
        )
        assert first == second
        assert first == tuple(sorted(set(first))) and len(first) == 6
        assert first not in blocked
        assert sampling.validate_sampled_ticket(formula, first) == first


def test_wheel_covers_every_candidate_triplet_and_exact_conditionals():
    from itertools import combinations
    research = importlib.import_module(PACKAGE + '.research_formulas')
    candidates = tuple(range(1, 9))
    assert len(list(research._pairings(candidates))) == 105
    for pairs in research._pairings(candidates):
        games = [set(candidates) - set(pair) for pair in pairs]
        assert {triple for game in games for triple in combinations(sorted(game), 3)} == set(combinations(candidates, 3))
        for inside, minimum in ((3, 3), (4, 3), (5, 4), (6, 5)):
            best = [max(len(set(winning) & game) for game in games)
                    for winning in combinations(candidates, inside)]
            assert min(best) == minimum


def test_diagnostic_and_crowd_metadata_are_explicitly_non_predictive():
    research = importlib.import_module(PACKAGE + '.research_formulas')
    rows = [tuple(sorted((start + i) % 45 + 1 for i in range(6))) for start in range(45)]
    diagnostic = research.fairness_diagnostic(rows)
    assert diagnostic['corrected_statistic'] == 0
    assert diagnostic['p_value'] == 1.0
    assert diagnostic['used_for_recommendations'] is False
    metadata = research.recommendation_details(research.CROWD_ID, (1, 2, 16, 27, 33, 45))
    assert metadata['purchase_data_available'] is False
    assert metadata['maximum_entropy_fitted'] is False
    assert metadata['expected_return_improvement'] is None
    assert metadata['predictive_evidence'] == 'not_established'
