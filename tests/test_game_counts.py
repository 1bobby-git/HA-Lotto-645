"""Per-formula multi-game generation (does not import Home Assistant)."""
import ast
import asyncio
import hashlib
import json
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
import voluptuous as vol

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'custom_components/lotto_645'
PACKAGE = 'lotto_game_batches_test'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(BASE)]
sys.modules[PACKAGE] = package
batches = __import__(PACKAGE + '.game_batches', fromlist=['game_batches'])
contract = __import__(PACKAGE + '.service_contract', fromlist=['service_contract'])
lab = __import__(PACKAGE + '.lab_client', fromlist=['lab_client'])
models = __import__(PACKAGE + '.models', fromlist=['models'])
methods_module = __import__(PACKAGE + '.methods', fromlist=['methods'])

Recommendation = models.Recommendation
AnalysisResult = models.AnalysisResult

UNIFORM = 'uniform_fisher_yates'
HOT = 'hot_numbers'
MAX = 10


def game(method_id, numbers, *, reason='생성', index=1):
    return Recommendation(
        index, method_id, method_id, 'core', tuple(sorted(numbers)), reason, None,
        {'target_round': 31}, source='core_service',
    )


def test_counts_only_accept_known_formulas_and_bounded_integers():
    raw = {UNIFORM: 3, HOT: 0, 'ghost_formula': 4, 'also_ghost': '5', UNIFORM + 'x': 99}
    assert batches.normalize_counts(raw, (UNIFORM, HOT)) == {UNIFORM: 3}
    assert batches.normalize_counts(None, (UNIFORM,)) == {}
    assert batches.normalize_counts('nope', (UNIFORM,)) == {}
    assert batches.requested_count({HOT: MAX}, HOT) == MAX
    assert batches.requested_count({HOT: MAX + 1}, HOT) == 1
    assert batches.requested_count({}, HOT) == 1


def test_first_batch_covers_the_whole_selection_and_stops_when_satisfied():
    ids = (UNIFORM, HOT)
    counts = {UNIFORM: 3, HOT: 1}
    collected = {}
    # Batch 0 always asks for every selected formula, so an existing single-game
    # result is reused rather than regenerated.
    assert batches.next_batch(ids, counts, collected) == ids
    collected[UNIFORM] = [game(UNIFORM, [1, 2, 3, 4, 5, 6])]
    collected[HOT] = [game(HOT, [7, 8, 9, 10, 11, 12])]
    # A formula already at its configured count never takes another batch.
    assert batches.next_batch(ids, counts, collected) == (UNIFORM,)
    collected[UNIFORM].append(game(UNIFORM, [13, 14, 15, 16, 17, 18]))
    assert batches.next_batch(ids, counts, collected) == (UNIFORM,)
    collected[UNIFORM].append(game(UNIFORM, [19, 20, 21, 22, 23, 24]))
    assert batches.next_batch(ids, counts, collected) == ()


def test_repeated_combination_is_not_counted_as_a_second_game():
    rows = [
        game(UNIFORM, [1, 2, 3, 4, 5, 6]),
        game(UNIFORM, [1, 2, 3, 4, 5, 6]),
        game(UNIFORM, [2, 3, 4, 5, 6, 7]),
    ]
    assert [row.numbers for row in batches.distinct_games(rows)] == [
        (1, 2, 3, 4, 5, 6),
        (2, 3, 4, 5, 6, 7),
    ]


def test_merge_orders_by_formula_and_numbers_each_formula_game():
    rows = batches.merge_batches(
        (UNIFORM, HOT),
        {UNIFORM: 2},
        {
            UNIFORM: [game(UNIFORM, [1, 2, 3, 4, 5, 6]), game(UNIFORM, [2, 3, 4, 5, 6, 7])],
            HOT: [game(HOT, [3, 4, 5, 6, 7, 8])],
        },
    )
    assert [(row.method_id, row.formula_game, row.index) for row in rows] == [
        (UNIFORM, 1, 1), (UNIFORM, 2, 2), (HOT, 1, 3),
    ]
    # The primary game of a formula keeps the numbers a template already reads.
    analysis = AnalysisResult(31, 30, rows, {})
    primary = analysis.recommendation_by_method(UNIFORM)
    assert primary.numbers == (1, 2, 3, 4, 5, 6)
    assert len(analysis.recommendations_by_method(UNIFORM)) == 2
    assert analysis.recommendations_by_method(HOT)[0].numbers == (3, 4, 5, 6, 7, 8)


def test_merge_drops_a_repeated_combination_from_the_second_slot():
    rows = batches.merge_batches(
        (UNIFORM,),
        {UNIFORM: 2},
        {UNIFORM: [game(UNIFORM, [1, 2, 3, 4, 5, 6]), game(UNIFORM, [1, 2, 3, 4, 5, 6])]},
    )
    assert [row.formula_game for row in rows] == [1]


def test_shortfall_reports_only_formulas_below_their_configured_count():
    rows = [game(UNIFORM, [1, 2, 3, 4, 5, 6])]
    # UNIFORM is two games short; HOT produced nothing at all.
    assert batches.shortfalls((UNIFORM, HOT), {UNIFORM: 3}, rows) == {UNIFORM: 2, HOT: 1}
    complete = [*rows, game(HOT, [1, 2, 3, 4, 5, 7])]
    assert batches.shortfalls((UNIFORM, HOT), {UNIFORM: 3, HOT: 1}, complete) == {UNIFORM: 2}
    assert batches.shortfalls((UNIFORM,), {UNIFORM: 1}, rows) == {}


def test_one_generation_can_answer_with_several_games_per_formula():
    def result(method_id, numbers):
        return {'formula_id': method_id, 'formula_version': '1', 'name': method_id,
                'category': 'cat', 'status': 'generated', 'numbers': numbers,
                'public_reason': 'r', 'reason_code': None}

    raw = {
        'contract_version': 1, 'generation_id': 'gen-1', 'request_key': 'req-1',
        'status': 'completed', 'target_round': 31, 'based_on_round': 30,
        'core_version': '1.26.0', 'generated_at': '2026-09-30T04:00:00+00:00',
        'results': [result(UNIFORM, [1, 2, 3, 4, 5, 6]),
                    result(UNIFORM, [2, 3, 4, 5, 6, 7]),
                    result(HOT, [3, 4, 5, 6, 7, 8])],
    }
    parsed = contract.Generation.parse(
        raw, expected_key='req-1', expected_target=31, requested_ids=(UNIFORM, HOT))
    counts = {key: sum(1 for g in parsed.games if g.formula_id == key) for key in (UNIFORM, HOT)}
    assert counts == {UNIFORM: 2, HOT: 1}
    # An unrequested formula is still a protocol violation.
    raw['results'].append(result('ghost_formula', [1, 2, 3, 4, 5, 6]))
    with pytest.raises(contract.ContractError, match='unexpected_output'):
        contract.Generation.parse(
            raw, expected_key='req-1', expected_target=31, requested_ids=(UNIFORM, HOT))


def _runtime_methods(*names):
    tree = ast.parse((BASE / 'service_runtime.py').read_text(encoding='utf-8'))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name in names
    ]


def _load_merge_batches():
    namespace = {
        'merge_batches': batches.merge_batches,
        'shortfalls': batches.shortfalls,
        'AnalysisResult': AnalysisResult,
    }
    methods = _runtime_methods('_merge_batches')
    exec(compile(ast.Module(body=methods, type_ignores=[]), '<runtime>', 'exec'), namespace)
    return namespace['_merge_batches']


def _load_batched_analysis():
    namespace = {'next_batch': batches.next_batch, 'MAX_GAMES_PER_FORMULA': MAX}
    methods = _runtime_methods('_batched_analysis')
    exec(compile(ast.Module(body=methods, type_ignores=[]), '<runtime>', 'exec'), namespace)
    return namespace['_batched_analysis']


def test_merged_summary_reports_counts_and_an_honest_shortfall():
    runtime = SimpleNamespace(
        owner=SimpleNamespace(selected_method_ids=(UNIFORM, HOT)), status='ready')
    merge = _load_merge_batches()
    saved = AnalysisResult(31, 30, (), {'core_version': '1.26.0', 'generation_id': 'gen-1'})
    partial = merge(runtime, {UNIFORM: 3, HOT: 1},
                    {UNIFORM: [game(UNIFORM, [1, 2, 3, 4, 5, 6])],
                     HOT: [game(HOT, [3, 4, 5, 6, 7, 8])]}, [saved])
    assert partial.summary['games_per_formula'] == {UNIFORM: 3, HOT: 1}
    assert partial.summary['game_shortfall'] == {UNIFORM: 2}
    assert 'game_shortfall_notice' in partial.summary
    assert partial.summary['batch_count'] == 1
    assert partial.summary['core_version'] == '1.26.0'
    full = merge(runtime, {UNIFORM: 1, HOT: 1},
                 {UNIFORM: [game(UNIFORM, [1, 2, 3, 4, 5, 6])],
                  HOT: [game(HOT, [3, 4, 5, 6, 7, 8])]}, [saved])
    assert full.summary['game_shortfall'] == {}
    assert 'game_shortfall_notice' not in full.summary


class Manager:
    """One durable batch slot that answers with the given games per request."""

    def __init__(self, games_per_call, start_error=None):
        self.games_per_call = list(games_per_call)
        self.start_error = start_error
        self.calls = 0
        self.formula_sets = []

    async def start(self, *, target_round, formula_ids, options, personal_profile,
                    personal_consent, context_tag, mode, source_generation_id,
                    material_context, nonce):
        self.calls += 1
        self.formula_sets.append(tuple(formula_ids))
        if self.start_error:
            raise self.start_error
        answer = self.games_per_call[min(self.calls - 1, len(self.games_per_call) - 1)]
        games = tuple(
            contract.PublicGame(method_id, '1', method_id, 'cat', 'generated',
                                tuple(sorted(numbers)), 'r', None)
            for method_id in formula_ids
            for numbers in answer
        )
        return contract.Generation('gen-1', 'k', 'completed', 31, 30, '1.26.0',
                                   '2026-09-30T04:00:00+00:00', games)


class Runtime:
    """Stand-in that runs the real batch loop and merge over stubbed managers."""

    _merge_batches = _load_merge_batches()

    def __init__(self, counts, managers, selected=(UNIFORM,)):
        self.managers = managers
        self.requested_batches = []
        self.owner = SimpleNamespace(
            selected_method_ids=tuple(selected),
            history=[SimpleNamespace(round=30)],
            formula_game_counts=dict(counts),
        )
        self.entry = SimpleNamespace(options={})
        self.client = object()
        self.catalog = SimpleNamespace(core_version='1.26.0')
        self.catalog_updated_at = float('inf')
        self.status = 'ready'
        self.connection_manager = SimpleNamespace(needs_refresh=False)
        self.info = {}

    def _remote_manager(self, index):
        self.requested_batches.append(index)
        return self.managers[index]

    async def _analysis(self, manager=None, ids=None):
        ids = tuple(self.owner.selected_method_ids if ids is None else ids)
        if manager is None:
            manager = self.managers[0]
        context = hashlib.sha256(json.dumps([31, list(ids)]).encode()).hexdigest()
        try:
            result = await manager.start(
                target_round=31, formula_ids=ids, options={}, personal_profile=None,
                personal_consent=False, context_tag=context, mode='generate',
                source_generation_id=None, material_context='material', nonce=0)
        except lab.LabServiceError:
            # The real worker keeps the previous result and records the error code.
            self.status = 'usage_limited'
            return AnalysisResult(31, 30, (), {'service_status': 'usage_limited'})
        rows = tuple(
            Recommendation(index, item.formula_id, item.name, item.category, item.numbers,
                           item.public_reason, None, {'target_round': 31}, source='core_service')
            for index, item in enumerate(result.games, start=1)
        )
        return AnalysisResult(31, 30, rows, {'core_version': result.core_version,
                                             'generation_id': result.generation_id})


def run_batches(counts, managers, *, selected=(UNIFORM,)):
    runtime = Runtime(counts, managers, selected)
    analysis = asyncio.run(_load_batched_analysis()(runtime))
    return runtime, analysis


def test_configured_counts_request_one_batch_per_outstanding_game():
    first = Manager([[[1, 2, 3, 4, 5, 6]]])
    second = Manager([[[2, 3, 4, 5, 6, 7]]])
    third = Manager([[[3, 4, 5, 6, 7, 8]]])
    runtime, analysis = run_batches({UNIFORM: 3}, {0: first, 1: second, 2: third})
    assert [call.calls for call in (first, second, third)] == [1, 1, 1]
    assert runtime.requested_batches == [0, 1, 2]
    assert [row.numbers for row in analysis.recommendations] == [
        (1, 2, 3, 4, 5, 6), (2, 3, 4, 5, 6, 7), (3, 4, 5, 6, 7, 8)
    ]
    assert [row.formula_game for row in analysis.recommendations] == [1, 2, 3]
    assert analysis.summary['game_shortfall'] == {}
    assert analysis.summary['batch_count'] == 3
    # Each batch owns its own durable job slot, so no manager is reused and a
    # restart can never collapse two games into one idempotency key.
    assert len({id(runtime.managers[index]) for index in (0, 1, 2)}) == 3


def test_a_server_returning_every_game_at_once_needs_no_extra_batch():
    single = Manager([[[1, 2, 3, 4, 5, 6], [2, 3, 4, 5, 6, 7], [3, 4, 5, 6, 7, 8]]])
    unused = Manager([[[9, 10, 11, 12, 13, 14]]])
    runtime, analysis = run_batches({UNIFORM: 3}, {0: single, 1: unused})
    assert single.calls == 1
    assert runtime.requested_batches == [0]
    assert len(analysis.recommendations) == 3
    assert [row.formula_game for row in analysis.recommendations] == [1, 2, 3]
    assert analysis.summary['game_shortfall'] == {}


def test_default_single_game_formula_stays_on_the_untouched_single_request_path():
    only = Manager([[[1, 2, 3, 4, 5, 6]]])
    runtime, analysis = run_batches({}, {0: only})
    assert only.calls == 1
    assert runtime.requested_batches == []
    assert len(analysis.recommendations) == 1
    # The unchanged single-game result keeps its own summary untouched.
    assert analysis.summary == {'core_version': '1.26.0', 'generation_id': 'gen-1'}


def test_a_batch_that_cannot_add_a_game_stops_instead_of_looping():
    first = Manager([[[1, 2, 3, 4, 5, 6]]])
    # Every later call answers with the same combination, so no batch can advance.
    repeat = Manager([[[1, 2, 3, 4, 5, 6]]])
    runtime, analysis = run_batches({UNIFORM: 4}, {0: first, 1: repeat, 2: repeat})
    assert [call.calls for call in (first, repeat)] == [1, 1]
    assert runtime.requested_batches == [0, 1]
    assert [row.numbers for row in analysis.recommendations] == [(1, 2, 3, 4, 5, 6)]
    assert analysis.summary['game_shortfall'] == {UNIFORM: 3}


def test_an_outage_keeps_the_accepted_games_and_reports_the_rest():
    first = Manager([[[1, 2, 3, 4, 5, 6]]])
    failing = Manager([[[2, 3, 4, 5, 6, 7]]], start_error=lab.LabServiceError('usage_limited'))
    runtime, analysis = run_batches({UNIFORM: 3}, {0: first, 1: failing, 2: failing})
    assert [row.numbers for row in analysis.recommendations] == [(1, 2, 3, 4, 5, 6)]
    assert analysis.summary['game_shortfall'] == {UNIFORM: 2}
    assert runtime.requested_batches == [0, 1]


def test_only_the_formulas_that_need_more_games_join_a_later_batch():
    plain = Manager([[[1, 2, 3, 4, 5, 6]]])
    extra = Manager([[[2, 3, 4, 5, 6, 7]]])
    runtime, analysis = run_batches(
        {UNIFORM: 1, HOT: 2}, {0: plain, 1: extra}, selected=(UNIFORM, HOT))
    # Batch 0 covers the whole selection; the second batch asks only for the
    # formula whose configured count is not satisfied yet.
    assert plain.formula_sets == [(UNIFORM, HOT)]
    assert extra.formula_sets == [(HOT,)]
    assert [row.method_id for row in analysis.recommendations] == [UNIFORM, HOT, HOT]
    assert [row.formula_game for row in analysis.recommendations] == [1, 1, 2]
    assert analysis.summary['game_shortfall'] == {}


def _flow_helpers(catalog=None):
    """Load the per-formula count form helpers without Home Assistant."""
    tree = ast.parse((BASE / 'config_flow.py').read_text(encoding='utf-8'))
    wanted = ('_game_count_fields', '_game_counts_schema', '_normalize_submitted_counts')
    methods = [n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name in wanted]
    assert len(methods) == len(wanted), 'per-formula count helpers are missing'

    class NumberSelectorMode:
        BOX = 'box'

    class NumberSelectorConfig:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class NumberSelector:
        # Real Home Assistant selectors are voluptuous validators.
        def __init__(self, config):
            self.config = config

        def __call__(self, value):
            return value

    namespace = {
        'vol': vol,
        'selector': SimpleNamespace(
            NumberSelector=NumberSelector,
            NumberSelectorConfig=NumberSelectorConfig,
            NumberSelectorMode=NumberSelectorMode,
        ),
        'Any': object,
        'METHODS_BY_ID': catalog or methods_module.METHODS_BY_ID,
        'requested_count': batches.requested_count,
        'DEFAULT_GAMES_PER_FORMULA': 1,
        'MAX_GAMES_PER_FORMULA': MAX,
    }
    exec(compile(ast.Module(body=methods, type_ignores=[]), '<config_flow>', 'exec'), namespace)
    return namespace


def test_each_selected_formula_gets_one_labelled_bounded_field():
    helpers = _flow_helpers()
    selected = [UNIFORM, HOT]
    fields = helpers['_game_count_fields'](selected)
    # Home Assistant renders an untranslated schema key verbatim, so the catalog
    # label becomes the on-screen field name without a translation entry.
    assert fields == {
        UNIFORM: methods_module.METHODS_BY_ID[UNIFORM].label,
        HOT: methods_module.METHODS_BY_ID[HOT].label,
    }
    schema = helpers['_game_counts_schema'](selected, {UNIFORM: 4, HOT: 2})
    rendered = {str(marker.schema): marker.default() for marker in schema.schema}
    assert rendered == {fields[UNIFORM]: 4, fields[HOT]: 2}
    for selector in schema.schema.values():
        assert selector.config.min == 1
        assert selector.config.max == MAX
        assert selector.config.step == 1


def test_an_unknown_formula_falls_back_to_the_stable_id_field():
    helpers = _flow_helpers()
    assert helpers['_game_count_fields'](['ghost_formula']) == {
        'ghost_formula': 'games_ghost_formula',
    }


def test_two_formulas_sharing_a_label_fall_back_to_the_id_field():
    shared = SimpleNamespace(label='같은 이름')
    catalog = {
        UNIFORM: shared,
        HOT: SimpleNamespace(label='다른 이름'),
    }
    helpers = _flow_helpers(catalog)
    # A duplicated label must not collapse two formulas onto one form field.
    assert helpers['_game_count_fields']([UNIFORM, HOT]) == {
        UNIFORM: '같은 이름', HOT: '다른 이름',
    }
    # A collision resolves to the stable ID form instead of overwriting a field.
    catalog[HOT] = shared
    assert helpers['_game_count_fields']([UNIFORM, HOT])[HOT] == f'games_{HOT}'


@pytest.mark.parametrize('submitted_value,expected', [(5, 5), (1, 1), (MAX, MAX)])
def test_a_submitted_count_survives_the_form_round_trip(submitted_value, expected):
    helpers = _flow_helpers()
    selected = [UNIFORM, HOT]
    fields = helpers['_game_count_fields'](selected)
    # The frontend posts the schema keys, i.e. the field names, not the formula IDs.
    posted = {fields[UNIFORM]: submitted_value, fields[HOT]: 1}
    assert helpers['_normalize_submitted_counts'](posted, selected) == {
        UNIFORM: expected, HOT: 1,
    }


@pytest.mark.parametrize('bad', [0, -1, MAX + 1, '3', 2.5, None])
def test_an_out_of_range_or_non_integer_count_never_survives(bad):
    helpers = _flow_helpers()
    selected = [UNIFORM]
    fields = helpers['_game_count_fields'](selected)
    posted = {fields[UNIFORM]: bad}
    assert helpers['_normalize_submitted_counts'](posted, selected) == {UNIFORM: 1}


def test_a_missing_field_falls_back_to_a_single_game():
    helpers = _flow_helpers()
    assert helpers['_normalize_submitted_counts']({}, [UNIFORM, HOT]) == {
        UNIFORM: 1, HOT: 1,
    }


def _coordinator_count_accessors():
    """Load the coordinator's game-count accessors without Home Assistant.

    Returns a class carrying the real property and method bodies.
    """
    tree = ast.parse((BASE / 'coordinator.py').read_text(encoding='utf-8'))
    wanted = {'formula_game_counts', 'game_count'}
    picked = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name in wanted:
            picked.append(node)
            wanted.discard(node.name)
    assert not wanted, f'coordinator lost {sorted(wanted)}'
    namespace = {
        'normalize_counts': batches.normalize_counts,
        'requested_count': batches.requested_count,
        'CONF_GAME_COUNTS': 'game_counts',
    }
    # The nodes keep their own decorators, so `formula_game_counts` arrives
    # already wrapped in `property` and must not be wrapped again.
    exec(compile(ast.Module(body=picked, type_ignores=[]), '<coordinator>', 'exec'), namespace)
    assert isinstance(namespace['formula_game_counts'], property)
    return type('Coordinator', (), {
        'configured_method_ids': (),
        'formula_game_counts': namespace['formula_game_counts'],
        'game_count': namespace['game_count'],
    })


def test_the_coordinator_count_accessors_filter_stored_options():
    """Exercise the real accessor bodies, which no test could import before.

    coordinator.py needs Home Assistant, so the property and method are lifted
    out by AST and given the helpers directly. This covers their filtering
    rules; `test_module_imports.py` is what proves the real module binds those
    helpers, because injecting them here would hide a missing import.
    """
    coordinator_class = _coordinator_count_accessors()

    def coordinator(options, configured=(UNIFORM, HOT)):
        instance = coordinator_class()
        instance.entry = SimpleNamespace(options=options)
        instance.configured_method_ids = configured
        return instance

    # Simply calling them is the regression check: an unbound helper name
    # raises NameError here exactly as it did during 2.4.7 setup.
    instance = coordinator({'game_counts': {UNIFORM: 4, HOT: 2}})
    assert instance.formula_game_counts == {UNIFORM: 4, HOT: 2}
    assert instance.game_count(UNIFORM) == 4
    assert instance.game_count(HOT) == 2

    # A formula left at the default, a deselected formula, junk and out-of-range
    # values must never leak into the configured counts.
    messy = coordinator({
        'game_counts': {
            UNIFORM: 4, HOT: 0, 'ghost_formula': 3,
            UNIFORM + 'x': '2', 'another_ghost': True,
        }
    })
    assert messy.formula_game_counts == {UNIFORM: 4}
    assert messy.game_count(HOT) == 1
    assert messy.game_count('ghost_formula') == 1

    # A user who never opened the count screen has no option at all.
    empty = coordinator({})
    assert empty.formula_game_counts == {}
    assert empty.game_count(UNIFORM) == 1
    assert empty.game_count('ghost_formula') == 1

    # A corrupted option must not break the accessors.
    for broken in (None, 'nope', 5, [1, 2], {UNIFORM: None}):
        damaged = coordinator({'game_counts': broken})
        assert damaged.formula_game_counts in ({}, {UNIFORM: 1})
        assert damaged.game_count(UNIFORM) == 1


