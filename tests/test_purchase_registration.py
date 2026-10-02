"""Register generated numbers as a purchased ticket (does not import Home Assistant)."""
import ast
import asyncio
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_analysis_engine import models

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'custom_components/lotto_645'
PACKAGE = 'lotto_register_test'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(BASE)]
sys.modules[PACKAGE] = package
purchases = __import__(PACKAGE + '.purchased_tickets', fromlist=['purchased_tickets'])
finalization = __import__(PACKAGE + '.finalization_purchase', fromlist=['finalization_purchase'])
# The coordinator uses the finalization book (imported as PurchaseBook).
PurchaseBook = finalization.FinalizationPurchaseBook

METHOD = 'hot_numbers'
ROUND = 40
NOW = __import__('datetime').datetime(2026, 9, 12, 7, tzinfo=__import__('datetime').UTC)


def _coordinator_methods(*names):
    tree = ast.parse((BASE / 'coordinator.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Lotto645Coordinator')
    nodes = [n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]
    assert len(nodes) == len(names), f'missing coordinator methods: {names}'
    ns = {
        'Any': object,
        'datetime': __import__('datetime').datetime,
        'UTC': __import__('datetime').UTC,
        'Recommendation': models.Recommendation,
        'AnalysisResult': models.AnalysisResult,
        'HomeAssistantError': type('HomeAssistantError', (Exception,), {}),
        'SLOTS': purchases.SLOTS,
        'parse_games': purchases.parse_games,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), 'coordinator', 'exec'), ns)
    return ns


def _game(index, numbers):
    return models.Recommendation(
        index, METHOD, METHOD, 'test', tuple(sorted(numbers)), 'reason', None,
        {'generated_at': '2026-09-12T06:20:00+00:00', 'generation_id': f'gen-{index}'},
        source='core_service', formula_game=index,
    )


class FakeStore:
    def __init__(self):
        self.saved = None

    async def async_save(self, payload):
        self.saved = payload


def _owner(games, book=None):
    analysis = models.AnalysisResult(ROUND, ROUND - 1, tuple(games), {})
    book = book if book is not None else PurchaseBook()
    owner = SimpleNamespace(
        purchase_storage_error=False,
        data=SimpleNamespace(analysis=analysis, ai_recommendation=None, ai_generated_at=None),
        purchase_book=book,
        _purchase_store=FakeStore(),
        _purchase_lock=asyncio.Lock(),
        _local_generated_at=NOW,
        _local_generation_nonce=9,
        service=SimpleNamespace(finalizer=None),
        async_update_listeners=lambda: None,
    )
    return owner


async def _run(owner, ns, method_id=METHOD, game_no=None):
    owner._async_write_purchase = ns['_async_write_purchase'].__get__(owner)
    owner._purchase_formula_links = ns['_purchase_formula_links'].__get__(owner)
    register = ns['async_register_generated_purchase'].__get__(owner)
    return await register(method_id, game_no)


def test_a_generated_game_fills_the_next_free_slot():
    ns = _coordinator_methods('async_register_generated_purchase', '_async_write_purchase',
                              '_purchase_formula_links')
    owner = _owner([_game(1, (1, 2, 3, 4, 5, 6))])
    result = asyncio.run(_run(owner, ns, game_no=1))
    assert result['round'] == ROUND
    assert result['registered'][0]['slot'] == 'A'
    assert result['registered'][0]['numbers'] == [1, 2, 3, 4, 5, 6]
    # The exact formula that produced the numbers is attached automatically.
    links = owner.purchase_book.records[str(ROUND)]['games'][0]['formula_links']
    assert links[0]['formula_id'] == METHOD
    assert links[0]['formula_game'] == 1


def test_a_full_ticket_starts_a_new_one():
    ns = _coordinator_methods('async_register_generated_purchase', '_async_write_purchase',
                              '_purchase_formula_links')
    book = PurchaseBook().updated(ROUND, {
        'game_a': '1 2 3 4 5 6', 'game_b': '2 3 4 5 6 7', 'game_c': '3 4 5 6 7 8',
        'game_d': '4 5 6 7 8 9', 'game_e': '5 6 7 8 9 10',
    }, now=NOW)
    owner = _owner([_game(1, (11, 13, 18, 22, 31, 32))], book=book)
    result = asyncio.run(_run(owner, ns, game_no=1))
    assert result['created_tickets'] == 1
    assert result['registered'][0]['slot'] == 'A'
    assert len(owner.purchase_book.tickets) == 2


def test_the_formula_button_registers_every_game_in_order():
    ns = _coordinator_methods('async_register_generated_purchase', '_async_write_purchase',
                              '_purchase_formula_links')
    owner = _owner([_game(1, (1, 2, 3, 4, 5, 6)), _game(2, (2, 3, 4, 5, 6, 7)),
                    _game(3, (11, 13, 18, 22, 31, 32))])
    result = asyncio.run(_run(owner, ns, game_no=None))
    assert [row['slot'] for row in result['registered']] == ['A', 'B', 'C']
    assert [row['formula_game'] for row in result['registered']] == [1, 2, 3]


def test_an_already_registered_number_is_skipped_not_duplicated():
    ns = _coordinator_methods('async_register_generated_purchase', '_async_write_purchase',
                              '_purchase_formula_links')
    book = PurchaseBook().updated(ROUND, {'game_a': '1 2 3 4 5 6'}, now=NOW)
    owner = _owner([_game(1, (1, 2, 3, 4, 5, 6)), _game(2, (2, 3, 4, 5, 6, 7))], book=book)
    result = asyncio.run(_run(owner, ns, game_no=None))
    assert [row['formula_game'] for row in result['registered']] == [2]
    assert result['skipped'] == [1]
    assert len(owner.purchase_book.records[str(ROUND)]['games']) == 2


def test_a_game_that_was_never_generated_is_rejected():
    ns = _coordinator_methods('async_register_generated_purchase', '_async_write_purchase',
                              '_purchase_formula_links')
    owner = _owner([_game(1, (1, 2, 3, 4, 5, 6))])
    with pytest.raises(ns['HomeAssistantError']):
        asyncio.run(_run(owner, ns, game_no=4))


def test_registration_is_refused_without_generated_data_or_a_healthy_store():
    ns = _coordinator_methods('async_register_generated_purchase', '_async_write_purchase',
                              '_purchase_formula_links')
    owner = _owner([_game(1, (1, 2, 3, 4, 5, 6))])
    owner.purchase_storage_error = True
    with pytest.raises(ns['HomeAssistantError']):
        asyncio.run(_run(owner, ns, game_no=1))
    owner.purchase_storage_error = False
    owner.data = None
    with pytest.raises(ns['HomeAssistantError']):
        asyncio.run(_run(owner, ns, game_no=1))


def test_a_failed_write_leaves_the_stored_purchase_untouched():
    ns = _coordinator_methods('async_register_generated_purchase', '_async_write_purchase',
                              '_purchase_formula_links')
    owner = _owner([_game(1, (11, 13, 18, 22, 31, 32))])
    before = owner.purchase_book.to_storage()

    class FailingStore(FakeStore):
        async def async_save(self, payload):
            raise OSError('disk full')

    owner._purchase_store = FailingStore()
    with pytest.raises(OSError):
        asyncio.run(_run(owner, ns, game_no=1))
    assert owner.purchase_book.to_storage() == before


def test_the_registration_command_is_admin_only_and_round_scoped():
    backend = (BASE / 'ticket_panel.py').read_text(encoding='utf-8')
    start = backend.index("'type': 'lotto_645/register_generated'")
    block = backend[start:start + 1400]
    assert 'websocket_api.require_admin' in block
    assert 'async_register_generated_purchase' in block
    # One command call must hand a refreshed view back so the UI updates once.
    assert "_view(coordinator, result['round'])" in block
    assert "'registration': result" in block
