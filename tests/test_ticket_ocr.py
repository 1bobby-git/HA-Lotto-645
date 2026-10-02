"""Synthetic ticket OCR regressions; no receipt identifiers or user photos."""
import ast
import asyncio
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'custom_components/lotto_645'
PACKAGE = 'lotto_ocr_test'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(BASE)]
sys.modules[PACKAGE] = package
ocr = __import__(PACKAGE + '.ticket_ocr', fromlist=['ticket_ocr'])

ROWS = [
    ['A', '1', '7', '12', '24', '33', '45'],
    ['B', '2', '11', '17', '25', '34', '42'],
    ['C', '1', '7', '12', '24', '33', '45'],  # Separate purchase of the same numbers.
    ['D', '5', '10', '18', '27', '36', '44'],
    ['E', '3', '11', '19', '28', '32', '41'],
]


def test_all_five_games_keep_slot_identity_and_identical_purchases():
    result = ocr.import_from_lines(ROWS, 5)
    assert result['game_count'] == 5
    assert result['values']['game_a'] == result['values']['game_c']
    assert result['values']['game_e'] == '3, 11, 19, 28, 32, 41'
    assert result['needs_review'] is False
    assert result['purchase_verified'] is False


@pytest.mark.parametrize('count', [1, 2, 3, 4])
def test_shorter_tickets_are_supported_and_unknown_count_is_reviewable(count):
    result = ocr.import_from_lines(ROWS[:count], count)
    assert result['game_count'] == count
    assert not result['needs_review']
    assert ocr.import_from_lines(ROWS[:count])['needs_review']


def test_missing_middle_or_last_row_is_never_collapsed_into_another_slot():
    for missing in (1, 4):
        result = ocr.import_from_lines(ROWS[:missing] + ROWS[missing+1:], 5)
        assert result['needs_review']
        assert result['missing_slots'] == ['ABCDE'[missing]]
        assert f"game_{'abcde'[missing]}" not in result['values']


def test_rereading_a_slot_does_not_duplicate_it_and_order_does_not_move_it():
    result = ocr.import_from_lines([ROWS[4], *ROWS, ROWS[4]], 5)
    assert result['game_count'] == 5
    assert list(result['values']) == [f'game_{slot}' for slot in 'abcde']
    assert not result['needs_review']


def test_conflicting_readings_require_review_and_do_not_pick_a_guess():
    result = ocr.import_from_lines([*ROWS, ['E', '4', '11', '19', '28', '32', '41']], 5)
    assert result['needs_review']
    assert result['missing_slots'] == ['E']
    assert 'game_e' not in result['values']


@pytest.mark.parametrize('tokens', [
    ['3', 'll', '19', '28', '32', '41'],
    ['3', '11', '19', '28', '32'],
    ['3', '11', '19', '28', '32', '41', '42'],
    ['0', '11', '19', '28', '32', '41'],
    ['3', '11', '19', '28', '32', '99'],
    ['3', '11', '19', '28', '32', '3'],
])
def test_bad_row_is_reviewable_and_is_not_guessed(tokens):
    result = ocr.import_from_lines([*ROWS[:4], ['E', *tokens]], 5)
    assert result['needs_review']
    assert result['missing_slots'] == ['E']
    assert 'game_e' not in result['values']


def test_legacy_unlabelled_rows_never_autosave():
    result = ocr.import_from_lines([row[1:] for row in ROWS], 5)
    assert result['needs_review']
    assert result['game_count'] == 5


def test_dates_serials_price_and_junk_are_not_games():
    for payload in (None, 'text', {}, [None], [[None]], [[[1]]], list(range(5000)),
                    [['2030/01/01']], [['12345']*6], [['5,000']], [['A', '1', '2']]):
        with pytest.raises(ValueError):
            ocr.import_from_lines(payload)


def _handler():
    tree = ast.parse((BASE / 'ticket_panel.py').read_text())
    node = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)
                and n.name == 'purchases_import_ocr')
    node.decorator_list = []
    owner = types.SimpleNamespace(async_save_purchase_record=AsyncMock())
    ns = {'__package__': PACKAGE, '_coordinator': lambda *_: owner,
          'parse_round': int, '_view': lambda *_: {'round': 2000},
          'PurchaseInputError': ocr.__dict__['parse_ticket'].__globals__['PurchaseInputError'],
          'HomeAssistantError': type('HomeAssistantError', (Exception,), {})}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                 'ticket_panel', 'exec'), ns)
    return owner, ns['purchases_import_ocr']


@pytest.mark.parametrize('preview,rows,expected,saves', [
    (True, ROWS, 5, 0), (False, ROWS[:4], 5, 0),
    (False, ROWS, 5, 1), (False, ROWS[:2], 2, 1),
    (False, [row[1:] for row in ROWS], 5, 0),
])
def test_websocket_preview_or_incomplete_import_never_touches_storage(preview, rows, expected, saves):
    owner, handler = _handler()
    results, errors = [], []
    connection = types.SimpleNamespace(send_result=lambda *args: results.append(args),
                                       send_error=lambda *args: errors.append(args))
    asyncio.run(handler(None, connection, {'id': 1, 'round': 2000, 'lines': rows,
        'preview': preview, 'expected_games': expected, 'revision': 'existing',
        'ticket_id': 'synthetic-existing', 'new_ticket': False}))
    assert owner.async_save_purchase_record.await_count == saves
    if not preview and not saves:
        assert not results
        assert errors[0][1] == 'ocr_review_required'
    else:
        assert not errors
        assert results[0][1]['imported']['saved'] is bool(saves)
    if saves:
        values = owner.async_save_purchase_record.call_args.args[1]
        assert len(values) == expected


def test_photo_preview_and_explicit_save_share_the_atomic_save_path():
    core = (BASE / 'www/lotto-panel-core.js').read_text()
    assert 'preview:true' in core
    assert '아직 저장하지 않았어요' in core
    assert "this.showEditorStep('edit')" in core
    assert 'tessedit_char_whitelist' not in core
    assert "tessedit_pageseg_mode:'7'" in core
    assert 'singleGameTokens(reread?.data)' in core


def test_provisional_slot_keeps_numbers_but_requires_review():
    rows = [*ROWS[:2], ['?C', *ROWS[2][1:]], *ROWS[3:]]
    result = ocr.import_from_lines(rows, 5)
    assert result['needs_review']
    assert result['game_count'] == 5
    assert result['values']['game_c'] == result['values']['game_a']
    extra = ocr.import_from_lines([ROWS[0], ['?B', *ROWS[1][1:]]], 1)
    assert extra['needs_review'] and extra['game_count'] == 2
