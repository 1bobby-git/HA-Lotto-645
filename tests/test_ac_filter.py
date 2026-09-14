"""AC is a shape constraint, never an additional prediction/score model."""
from collections import Counter
from itertools import combinations
import importlib.util
import json
from math import comb
from pathlib import Path
import random
from types import SimpleNamespace

import pytest
from test_sampling import sampling, methods, cache, ScriptRng, ZeroRng

AC = sampling.AC_FILTER_ID
EXAMPLE = (2, 5, 11, 17, 21, 33)
ROOT = Path(__file__).resolve().parents[1]


def reference_ac(row):
    mask = 0
    for a, b in combinations(row, 2):
        mask |= 1 << abs(a - b)
    return mask.bit_count() - 5


def test_definition_uses_all_pairs_and_public_example():
    assert sampling.ac_value(EXAMPLE) == 7
    assert sampling.ac_value(reversed(EXAMPLE)) == 7
    assert sampling.ac_value((1, 2, 3, 4, 5, 6)) == 0
    assert sampling.ac_value((1, 2, 5, 11, 19, 24)) == 10
    # Translation preserves pair differences, unlike delta's first entry.
    assert sampling.ac_value(tuple(n + 1 for n in EXAMPLE)) == 7


@pytest.mark.parametrize('row', [(), (1, 2), (1, 1, 3, 4, 5, 6),
                                (True, 2, 3, 4, 5, 6), (1., 2, 3, 4, 5, 6),
                                (0, 2, 3, 4, 5, 6), (1, 2, 3, 4, 5, 46)])
def test_invalid_ac_input_fails_closed(row):
    with pytest.raises(ValueError):
        sampling.ac_value(row)


def test_reference_agrees_on_entire_small_space():
    for row in combinations(range(1, 16), 6):
        assert sampling.ac_value(row) == reference_ac(row)


@pytest.mark.parametrize('fixed', [(), (7,), (7, 21), EXAMPLE[:3], EXAMPLE[:5], EXAMPLE])
def test_generation_fixed_numbers_and_seeded_reproduction(fixed):
    for seed in range(20):
        ticket = sampling.generate_ticket(AC, fixed, rng=random.Random(seed))
        assert ticket == sampling.generate_ticket(AC, fixed, rng=random.Random(seed))
        assert ticket == tuple(sorted(set(ticket))) and len(ticket) == 6
        assert set(fixed) <= set(ticket) and reference_ac(ticket) >= 7


def test_exact_small_space_is_uniform_over_allowed_not_ac_bins():
    fixed = EXAMPLE[:5]
    blocked = {EXAMPLE}
    expected = {tuple(sorted((*fixed, n))) for n in range(1, 46) if n not in fixed}
    expected = {t for t in expected if reference_ac(t) >= 7} - blocked
    counts = Counter(sampling.generate_ticket(AC, fixed, excluded_combinations=blocked,
                                             rng=ScriptRng((i,)))
                     for i in range(len(expected)))
    assert set(counts) == expected and set(counts.values()) == {1}


def test_impossible_fixed_and_exhausted_filtered_space_do_not_relax():
    with pytest.raises(ValueError, match='AC 7'):
        sampling.generate_ticket(AC, (1, 2, 3, 4, 5, 6), rng=ZeroRng())
    fixed = EXAMPLE[:5]
    allowed = [tuple(sorted((*fixed, n))) for n in range(1, 46) if n not in fixed]
    allowed = [t for t in allowed if reference_ac(t) >= 7]
    with pytest.raises(ValueError, match='AC 7'):
        sampling.generate_ticket(AC, fixed, excluded_combinations=allowed, rng=ZeroRng())


def test_rejection_is_bounded_and_no_unrestricted_fallback():
    class CountedZero(ZeroRng):
        calls = 0
        def randrange(self, stop):
            self.calls += 1
            return super().randrange(stop)
    rng = CountedZero()
    with pytest.raises(ValueError, match='상한'):
        sampling.generate_ticket(AC, rng=rng)
    assert rng.calls == 6 * sampling.AC_MAX_ATTEMPTS


def test_rejection_does_not_accept_bad_ac_or_blocked_good_ac(monkeypatch):
    other = (3, 6, 12, 18, 22, 34)
    proposals = iter(((1, 2, 3, 4, 5, 6), EXAMPLE, other))
    monkeypatch.setattr(sampling, 'fisher_yates', lambda *args: next(proposals))
    assert sampling.generate_ticket(AC, excluded_combinations=(EXAMPLE,), rng=ZeroRng()) == other


def test_csprng_wiring_and_no_history_weighting(monkeypatch):
    calls = []
    def factory():
        calls.append(True)
        return random.Random(12)
    monkeypatch.setattr(sampling, 'SystemRandom', factory)
    assert reference_ac(sampling.generate_ticket(AC)) >= 7 and calls == [True]
    a = sampling.generate_ticket(AC, history=(), rng=random.Random(18))
    b = sampling.generate_ticket(AC, history=[(1, 2, 3, 4, 5, 6)] * 300, rng=random.Random(18))
    assert a == b


def test_additive_catalog_defaults_legacy_ids_and_consensus_eligibility():
    assert len(methods.METHODS) == 24
    assert AC not in sampling.UNIFORM_IDS and AC not in methods.DEFAULT_METHOD_IDS
    assert methods.DEFAULT_METHOD_IDS == ('uniform_fisher_yates', 'uniform_floyd',
        'uniform_rejection', 'uniform_sequential', 'calibrated_stratified')
    assert methods.METHODS_BY_ID[AC].sampling == AC
    assert methods.METHODS_BY_ID[AC].weights == {}
    assert methods.normalize_method_ids([AC, AC, 'delta_system']) == (AC, 'delta_system')
    assert methods.consensus_source_ids([AC, 'uniform_floyd', methods.METHOD_SELECTED_MEDIAN]) == (AC, 'uniform_floyd')
    assert not methods.is_score_formula(AC)
    assert any(o['value'] == AC for o in methods.method_selector_options())


def test_cache_restores_good_ac_and_rejects_structurally_bad_ticket():
    history = [SimpleNamespace(round=1, numbers=(1, 2, 3, 4, 5, 6), bonus=7)]
    record = {'key': cache.cache_key(history, [AC], 0), 'tickets': {AC: list(EXAMPLE)}}
    assert cache.restore_tickets(record, history, [AC], 0) == {AC: EXAMPLE}
    record['tickets'][AC] = [7, 8, 9, 10, 11, 12]  # Valid six numbers, but AC=0.
    assert cache.restore_tickets(record, history, [AC], 0) == {}
    with pytest.raises(ValueError, match='AC 7'):
        sampling.validate_sampled_ticket(AC, (7, 8, 9, 10, 11, 12))


def test_independent_full_space_report_and_reference_script():
    report = json.loads((ROOT / 'docs/ac-space-verification.json').read_text())
    assert report['scope'] == 'all_combinations_not_historical_draws'
    assert report['total_combinations'] == comb(45, 6)
    assert sum(report['ac_histogram'].values()) == comb(45, 6)
    assert sum(report['ac_histogram'][str(i)] for i in range(7, 11)) == sampling.AC_ALLOWED_COMBINATIONS
    assert report['ac_ge_7_count'] == 6_943_080
    assert report['predictive_evidence'] is False
    spec = importlib.util.spec_from_file_location('ac_reference_script', ROOT / 'scripts/verify_ac_space.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    small = module.enumerate_space(15)
    expected = Counter(reference_ac(row) for row in combinations(range(1, 16), 6))
    assert small['ac_histogram'] == {str(i): expected[i] for i in range(11)}


def test_engine_ac_metadata_exclusions_restoration_and_consensus():
    from test_analysis_engine import analysis, _history
    history = _history(40)
    blocked = {EXAMPLE, (7, 8, 9, 10, 11, 12)}
    selected = (AC, 'uniform_fisher_yates', methods.METHOD_SELECTED_MEDIAN)
    result = analysis.build_analysis(history, selected, excluded_combinations=tuple(blocked), rng=random.Random(14))
    rec = result.recommendation_by_method(AC)
    past = {d.numbers for d in history}
    expected_count = sampling.AC_ALLOWED_COMBINATIONS - sum(reference_ac(t) >= 7 for t in blocked | past)
    assert rec.numbers not in blocked | past
    assert rec.score is None and rec.details['ac_value'] == reference_ac(rec.numbers)
    assert rec.details['eligible_combination_count'] == expected_count
    assert rec.details['history_used_for_weighting'] is False
    assert rec.details['uniformity'] == 'uniform_over_ac_filtered_allowed_combinations'
    assert rec.details['first_prize_odds'] == '1/8,145,060'
    assert f"AC {reference_ac(rec.numbers)}" in rec.reason
    assert result.recommendation_by_method(methods.METHOD_SELECTED_MEDIAN).details['consensus_source_count'] == 2
    stored = cache.store_tickets(result, history, selected, 0)
    restored = cache.restore_tickets(stored, history, selected, 0)
    again = analysis.build_analysis(history, selected, restored_tickets=restored)
    assert [r.numbers for r in again.recommendations] == [r.numbers for r in result.recommendations]
    with pytest.raises(ValueError, match='AC 7'):
        analysis.build_analysis(history, (AC,), restored_tickets={AC: (7, 8, 9, 10, 11, 12)})
