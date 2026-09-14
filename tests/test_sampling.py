"""Exact finite-space proofs, CSPRNG wiring and honest AI/cache boundaries."""
from collections import Counter
from fractions import Fraction
import importlib
from itertools import combinations
from math import comb
from pathlib import Path
import random
import sys
import types

import pytest

PACKAGE = '_lotto_sampling_tests'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'custom_components/lotto_645')]
sys.modules[PACKAGE] = package
sampling = importlib.import_module(PACKAGE + '.sampling')
methods = importlib.import_module(PACKAGE + '.methods')
ai = importlib.import_module(PACKAGE + '.ai_formula')
cache = importlib.import_module(PACKAGE + '.formula_cache')
models = importlib.import_module(PACKAGE + '.models')


class MoreChoices(Exception):
    def __init__(self, count):
        self.count = count


class ScriptRng:
    def __init__(self, choices):
        self.values = iter(choices)

    def randrange(self, stop):
        value = next(self.values, None)
        if value is None:
            raise MoreChoices(stop)
        assert 0 <= value < stop
        return value


@pytest.mark.parametrize('formula', [f for f in sampling.UNIFORM_IDS if f != 'uniform_rejection'])
def test_exact_distribution_by_enumerating_every_rng_branch(formula):
    # Different bucket capacities ensure CCSS is combinatorially weighted.
    pool = (1, 2, 11, 12, 13, 41)
    distribution = Counter()
    pending = [((), Fraction(1))]
    while pending:
        path, probability = pending.pop()
        try:
            ticket = sampling.SAMPLERS[formula](pool, 3, ScriptRng(path))
        except MoreChoices as event:
            pending.extend(((*path, i), probability / event.count) for i in range(event.count))
        else:
            distribution[ticket] += probability
    assert set(distribution) == set(combinations(pool, 3))
    assert set(distribution.values()) == {Fraction(1, comb(len(pool), 3))}


@pytest.mark.parametrize('formula', sampling.UNIFORM_IDS + (sampling.BAYESIAN_ID,))
@pytest.mark.parametrize('fixed', [(), (7,), (7, 21), (1, 11, 21, 31, 41), (1, 2, 3, 4, 5, 6)])
def test_validity_fixed_numbers_and_reproducible_injected_rng(formula, fixed):
    first = sampling.generate_ticket(formula, fixed, rng=random.Random(42))
    assert first == sampling.generate_ticket(formula, fixed, rng=random.Random(42))
    assert len(first) == len(set(first)) == 6
    assert first == tuple(sorted(first))
    assert set(fixed).issubset(first) and all(1 <= n <= 45 for n in first)


@pytest.mark.parametrize('fixed', [(0,), (46,), (True,), (1.0,), (1, 1), tuple(range(1, 8))])
def test_invalid_fixed_input_is_rejected(fixed):
    with pytest.raises(ValueError):
        sampling.generate_ticket('calibrated_stratified', fixed)


def test_ccss_weights_sum_to_exact_combination_count():
    for capacities in [(10, 10, 10, 10, 5), (8, 9, 10, 10, 3), (0, 0, 0, 1, 1)]:
        for k in range(min(6, sum(capacities)) + 1):
            allocations, cdf = sampling.allocation_table(capacities, k)
            assert cdf[-1] == comb(sum(capacities), k)
            assert all(sum(x) == k for x in allocations)
            assert all(a < b for a, b in zip((0, *cdf), cdf))


def test_unranking_is_bijective_for_every_small_space():
    for n in range(1, 10):
        pool = tuple(range(n))
        for k in range(n + 1):
            for rank, subset in enumerate(combinations(pool, k)):
                assert sampling.unrank(pool, k, rank) == subset
                assert sampling.rank_subset(pool, subset) == rank


class ZeroRng:
    def randrange(self, stop):
        assert stop > 0
        return 0


def test_exclusion_fallback_stays_inside_allowed_space_and_terminates():
    fixed = (1, 2, 3, 4, 5)
    allowed = fixed + (45,)
    blocked = [fixed + (n,) for n in range(6, 45)]
    for formula in sampling.UNIFORM_IDS:
        assert sampling.generate_ticket(formula, fixed, excluded_combinations=blocked, rng=ZeroRng()) == allowed
    with pytest.raises(ValueError, match='새 조합'):
        sampling.generate_ticket('uniform_floyd', fixed, excluded_combinations=blocked + [allowed])
    assert len(sampling.rejection(sampling.NUMBERS, 6, ZeroRng())) == 6


def test_production_constructs_os_rng_not_seeded_random(monkeypatch):
    calls = []
    def factory():
        calls.append(True)
        return random.Random(1)
    monkeypatch.setattr(sampling, 'SystemRandom', factory)
    sampling.generate_ticket('uniform_fisher_yates')
    assert calls == [True]


def test_bayesian_integer_weights_match_the_report_without_amplification():
    history = [tuple(range(1, 7))] * 300
    weights = sampling.frequency_weights(history)
    total = sum(weights.values())
    for n in sampling.NUMBERS:
        posterior = ((300 if n <= 6 else 0) + 500 * 6 / 45) / 800
        assert weights[n] / total == pytest.approx(.95 / 45 + .05 * posterior / 6)
    assert set(sampling.frequency_weights(history, history_mix=0).values()) == {6 * 800}
    with pytest.raises(ValueError):
        sampling.frequency_weights(history, history_mix=.11)
    # Lookback is restricted to the training prefix; no target is accepted here.
    assert sampling.frequency_weights([tuple(range(40, 46))] + history) == weights


def test_ai_cannot_supply_numbers_or_change_the_formula():
    good = {'formula_id': ai.AI_BASE_FORMULA, 'reason': '조합 개수로 보정한 CCSS 추첨입니다.'}
    assert ai.validate_explanation(good)[0] == good['reason']
    for patch in ({'number_1': 7}, {'numbers': [1,2,3,4,5,6]}, {'formula_id': 'hot_numbers'}, {'reason': ''}):
        with pytest.raises(ValueError):
            ai.validate_explanation(good | patch)
    prompt = ai.explanation_prompt((1,2,3,4,5,6), 1242, 1241)
    assert 'number_1' not in prompt and '"predictive_claim": false' in prompt
    assert '"history_used_for_weighting": false' in prompt


def test_semantic_aliases_preserve_old_ids_and_prefer_formula_key():
    assert methods.resolve_formula({'method': 'old', 'formula': 'new'}, 'default') == 'new'
    assert methods.resolve_formula({'method': 'old'}, 'default') == 'old'
    rec = models.Recommendation(1, 'uniform_floyd', 'Floyd', '균등', (1,2,3,4,5,6), 'r', None, {})
    restored = models.Recommendation.from_storage(rec.to_storage())
    assert restored == rec
    assert rec.as_attributes()['formula_id'] == rec.as_attributes()['method_id']
    with pytest.raises(ValueError):
        models.Recommendation.from_storage(rec.to_storage() | {'numbers': [True,2,3,4,5,6]})


def test_cache_is_invalidated_by_round_sequence_selection_and_history_correction():
    draw = models.LottoDraw(1, '2002-12-07', (1,2,3,4,5,6), 7)
    rec = models.Recommendation(1, 'uniform_floyd', 'Floyd', '균등', (10,11,12,13,14,15), 'r', None, {})
    result = models.AnalysisResult(2, 1, (rec,), {})
    stored = cache.store_tickets(result, [draw], ['uniform_floyd'], 0)
    assert cache.restore_tickets(stored, [draw], ['uniform_floyd'], 0) == {'uniform_floyd': rec.numbers}
    assert not cache.restore_tickets(stored, [draw], ['uniform_floyd'], 1)
    assert not cache.restore_tickets(stored, [draw], ['uniform_sequential'], 0)
    changed = models.LottoDraw(1, '2002-12-07', (1,2,3,4,5,8), 7)
    assert not cache.restore_tickets(stored, [changed], ['uniform_floyd'], 0)


def test_ai_backend_excludes_local_past_and_previous_ai_tickets():
    draw = models.LottoDraw(30, '2003-07-01', (1,2,3,4,5,6), 7)
    rec = models.Recommendation(1, 'uniform_floyd', 'Floyd', '균등', (10,11,12,13,14,15), 'r', None, {})
    previous = models.Recommendation(2, 'home_assistant_ai', 'AI', 'AI', (20,21,22,23,24,25), 'r', None, {})
    result = models.AnalysisResult(31, 30, (rec,), {})
    ticket = ai.make_ai_ticket([draw], [rec], previous, rng=random.Random(21))
    assert ticket not in {draw.numbers, rec.numbers, previous.numbers}
    assert ai.validate_backend_ticket(ticket, result, [draw]) == ticket
