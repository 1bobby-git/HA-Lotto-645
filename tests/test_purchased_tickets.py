"""Pure round-scoped purchase checking; all numbers here are synthetic fixtures."""
from copy import deepcopy
from datetime import UTC, datetime
import json
import importlib

import pytest
from test_analysis_engine import models

purchases = importlib.import_module('custom_components.lotto_645.purchased_tickets')
evaluator = importlib.import_module('custom_components.lotto_645.result_evaluator')
DRAW = models.LottoDraw(40, '2003-09-06', (1, 2, 3, 4, 5, 6), 7)
NOW = datetime(2026, 9, 12, 7, tzinfo=UTC)
GOOD = '1, 2, 3, 4, 5, 6'


@pytest.mark.parametrize('value', [GOOD, '6 5 4 3 2 1', '01/02/03/04/05/06',
                                  '01;02;03;04;05;06', '010203040506',
                                  '１，２，３，４，５，６', [6, 5, 4, 3, 2, 1]])
def test_canonical_six_numbers(value):
    assert purchases.parse_ticket(value) == (1, 2, 3, 4, 5, 6)


@pytest.mark.parametrize('value', ['', '123456', '1 2 3 4 5', '1 2 3 4 5 6 7',
                                  '1 1 2 3 4 5', '0 1 2 3 4 5', '1 2 3 4 5 46',
                                  '1.0 2 3 4 5 6', '1 -2 3 4 5 6', '1e0 2 3 4 5 6',
                                  [True, 2, 3, 4, 5, 6], [1., 2, 3, 4, 5, 6],
                                  ['1', '2', '3', '4', '5', '6'], None])
def test_invalid_or_ambiguous_ticket_rejected(value):
    with pytest.raises(purchases.PurchaseInputError) as error:
        purchases.parse_ticket(value, 'game_c')
    assert error.value.field == 'game_c'
    assert error.value.code == 'invalid_purchase_numbers'


@pytest.mark.parametrize('value', [0, -1, 'abc', True, 1.5, '1.0', '1240회', '1000000'])
def test_invalid_round(value):
    with pytest.raises(purchases.PurchaseInputError):
        purchases.parse_round(value)


def test_up_to_five_games_same_numbers_on_two_real_lines_are_not_deduplicated():
    fields = {f'game_{slot.lower()}': GOOD for slot in purchases.SLOTS}
    book = purchases.PurchaseBook().updated(40, fields, now=NOW)
    assert len(book.records['40']['games']) == 5
    assert [r['slot'] for r in book.records['40']['games']] == list('ABCDE')
    assert book.report([DRAW])['winning_game_count'] == 5
    assert book.report([DRAW])['purchase_verified'] is False


def test_sparse_slots_are_preserved_and_empty_not_a_losing_game():
    book = purchases.PurchaseBook().updated(40, {'game_a': '', 'game_c': GOOD, 'game_e': GOOD}, now=NOW)
    assert [r['slot'] for r in book.records['40']['games']] == ['C', 'E']
    with pytest.raises(purchases.PurchaseInputError, match='purchase_games_required'):
        book.updated(41, {'game_a': ''})


def test_atomic_validation_does_not_overwrite_existing_or_other_rounds():
    book = purchases.PurchaseBook().updated(40, {'game_a': GOOD}, now=NOW)
    book = book.updated(41, {'game_b': '10 11 12 13 14 15'}, now=NOW)
    original = book.to_storage()
    with pytest.raises(purchases.PurchaseInputError):
        book.updated(40, {'game_a': '7 8 9 10 11 12', 'game_e': 'bad'})
    assert book.to_storage() == original
    replaced = book.updated(40, {'game_c': GOOD}, now=NOW)
    assert replaced.records['41'] == original['records']['41']
    assert replaced.form_values(40) == {'game_c': GOOD}
    assert book.records['40']['games'][0]['slot'] == 'A'


def test_round_scoped_restart_and_clear():
    book = purchases.PurchaseBook().updated(40, {'game_a': GOOD}, now=NOW)
    book = book.updated(41, {'game_b': GOOD}, now=NOW)
    stored = json.loads(json.dumps(book.to_storage()))
    restored = purchases.PurchaseBook.from_storage(stored)
    assert restored.report([DRAW])['status'] == 'waiting'  # selected round41
    assert restored.report([DRAW])['losing_game_count'] == 0
    assert restored.report([DRAW], 40)['highest_prize'] == '1등'
    cleared = restored.updated(40, {}, clear=True)
    assert set(cleared.records) == {'41'} and cleared.selected_round == 41
    assert cleared.updated(41, {}, clear=True).report([])['status'] == 'not_registered'
    stored['records']['41']['games'][0]['numbers'][0] = 45
    assert restored.records['41']['games'][0]['numbers'][0] == 1


@pytest.mark.parametrize('mutate', [
    lambda x: x.update(version=99),
    lambda x: x.update(records=[]),
    lambda x: x['records']['40'].update(round=41),
    lambda x: x['records']['40'].update(saved_at='no-date'),
    lambda x: x['records']['40'].update(saved_at='2026-09-12T00:00:00'),
    lambda x: x['records']['40'].update(games=[]),
    lambda x: x['records']['40']['games'][0].update(numbers=[1, 1, 2, 3, 4, 5]),
    lambda x: x['records']['40']['games'][0].update(slot='F'),
    lambda x: x['records']['40']['games'].append(deepcopy(x['records']['40']['games'][0])),
])
def test_bad_storage_is_rejected_not_reset(mutate):
    payload = purchases.PurchaseBook().updated(40, {'game_a': GOOD}, now=NOW).to_storage()
    mutate(payload)
    with pytest.raises((ValueError, TypeError)):
        purchases.PurchaseBook.from_storage(payload)


@pytest.mark.parametrize('numbers,prize,matches,bonus', [
    ((1, 2, 3, 4, 5, 6), '1등', 6, False),
    ((1, 2, 3, 4, 5, 7), '2등', 5, True),
    ((1, 2, 3, 4, 5, 8), '3등', 5, False),
    ((1, 2, 3, 4, 7, 8), '4등', 4, True),
    ((1, 2, 3, 7, 8, 9), '5등', 3, True),
    ((1, 2, 7, 8, 9, 10), '미당첨', 2, True),
])
def test_purchase_prize_levels_same_evaluator(numbers, prize, matches, bonus):
    book = purchases.PurchaseBook().updated(40, {'game_a': numbers}, now=NOW)
    report = book.report([DRAW])
    row = report['games'][0]
    assert row['prize'] == prize and row['main_match_count'] == matches
    assert row['bonus_match'] is bonus
    assert row['source'] == 'purchased' and row['method_id'] == 'purchased_A'


def test_combination_separates_recommendations_from_purchases_and_wrong_rounds():
    recommendation = models.Recommendation(1, 'test', '테스트 추천', 'stats',
                                           (1, 2, 3, 20, 21, 22), 'reason', .5, {})
    evaluated = evaluator.evaluate_recommendations(DRAW, [recommendation], evaluated_at=NOW)
    book = purchases.PurchaseBook().updated(40, {'game_a': GOOD, 'game_e': '20 21 22 23 24 25'}, now=NOW)
    report = purchases.combined_result(DRAW, evaluated, book.report([DRAW]))
    assert report['checked_game_count'] == 3
    assert report['recommendation_game_count'] == 1 and report['purchased_game_count'] == 2
    assert report['winning_game_count'] == 2 and report['losing_game_count'] == 1
    assert report['highest_prize_sensor'] == '직접 구매 A'
    wrong = deepcopy(evaluated); wrong['round'] = 39
    assert purchases.combined_result(DRAW, wrong, book.report([DRAW]))['checked_game_count'] == 2
    waiting = purchases.PurchaseBook().updated(41, {'game_a': GOOD}, now=NOW).report([DRAW])
    no_record = purchases.combined_result(DRAW, None, waiting)
    assert no_record['status'] == 'no_saved_tickets'
    assert no_record['losing_game_count'] == 0 and no_record['highest_prize'] is None


def test_manual_purchase_may_equal_an_old_winning_combination():
    # Real tickets are never run through recommendation history-exclusion rules.
    book = purchases.PurchaseBook().updated(41, {'game_a': list(DRAW.numbers)}, now=NOW)
    assert book.form_values(41)['game_a'] == GOOD


def test_sixth_game_rejected_not_silently_discarded():
    with pytest.raises(purchases.PurchaseInputError, match='purchase_game_limit'):
        purchases.PurchaseBook().updated(40, {f'game_{s}': GOOD for s in 'abcdef'}, now=NOW)
