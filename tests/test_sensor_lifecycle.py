"""Configured game lifecycle over real durable generation code, without live HA/Core."""
import ast
import asyncio
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
import hashlib
import importlib
import json
import time
from types import SimpleNamespace

from test_game_counts import BASE, PACKAGE, AnalysisResult, HOT, UNIFORM, batches, contract, lab
from test_game_entities import entities

remote = importlib.import_module(PACKAGE + '.remote_generation')


def runtime_methods():
    wanted = {'_analysis', '_batched_analysis', '_merge_batches', '_previous_analysis',
              'analysis_from_saved', '_finish_or_schedule', '_follow'}
    tree = ast.parse((BASE / 'service_runtime.py').read_text(encoding='utf-8'))
    nodes = [node for node in ast.walk(tree)
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted]
    namespace = {
        'asyncio': asyncio, 'hashlib': hashlib, 'json': json, 'time': time,
        'datetime': datetime, 'asdict': asdict, 'LabServiceError': lab.LabServiceError,
        'retry_due': remote.retry_due, 'numbers': contract.numbers,
        'Recommendation': batches.Recommendation, 'AnalysisResult': AnalysisResult,
        'merge_batches': batches.merge_batches, 'next_batch': batches.next_batch,
        'shortfalls': batches.shortfalls, 'MAX_GAMES_PER_FORMULA': 10,
        'CONF_PERSONAL_CONSENT': 'personal_consent', 'METHOD_MYUNGRI_HETU': 'saju',
        'METHODS_BY_ID': {key: SimpleNamespace(status='active') for key in (UNIFORM, HOT)},
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<service_runtime>', 'exec'), namespace)
    return {name: namespace[name] for name in wanted}


class MemoryStore:
    def __init__(self):
        self.value = None

    async def async_load(self):
        return deepcopy(self.value)

    async def async_save(self, value):
        self.value = deepcopy(value)


class Core:
    """Deterministic server double honoring the existing reconciliation contract."""
    def __init__(self):
        self.calls = []
        self.results = {}

    async def async_generate(self, **kwargs):
        self.calls.append(kwargs)
        old = self.results.get(kwargs['source_generation_id'])
        kept = {game.formula_id: game for game in old.games} if old and kwargs['mode'] == 'reconcile' else {}
        offset = len(self.calls)
        games = tuple(kept.get(key) or contract.PublicGame(
            key, '1', key, 'test', 'generated', tuple(range(offset, offset + 6)), 'reason', None
        ) for key in kwargs['formula_ids'])
        result = contract.Generation(
            f'gen-{offset}', kwargs['request_key'], 'completed', 31, 30, '1.26.0',
            '2026-10-05T03:00:00+00:00', games)
        self.results[result.generation_id] = result
        return result


class Runtime(type('ProductionMethods', (), runtime_methods())):
    def __init__(self, core, stores, counts, selected=(UNIFORM,), disconnected=False):
        self.core, self.stores = core, stores
        self.client = None if disconnected else core
        self.generators = {}
        self.generator = None if disconnected else self._remote_manager(0)
        self.catalog = SimpleNamespace(core_version='1.26.0')
        self.catalog_updated_at = time.monotonic()
        self.connection_manager = SimpleNamespace(needs_refresh=False)
        self.entry = SimpleNamespace(options={})
        self.status = 'ready'
        self.retry_tasks = set()
        self.owner = SimpleNamespace(
            selected_method_ids=tuple(selected), formula_game_counts=counts,
            history=[SimpleNamespace(round=30)], saju_profile=None,
            _local_generation_nonce=0, _needs_storage_save=False,
        )

    def _remote_manager(self, index):
        if index not in self.generators:
            self.generators[index] = remote.RemoteGeneration(
                self.client, self.stores.setdefault(index, MemoryStore()))
        return self.generators[index]

    async def prepare(self):
        self.client = self.core
        self.generator = self._remote_manager(0)

    def material_context(self, options, profile):
        return 'unchanged-material'

    def legacy_analysis(self, ids):
        return AnalysisResult(31, 30, (), {})


def test_restart_and_count_changes_fill_new_slots_without_replacing_retained_numbers():
    async def scenario():
        core, stores = Core(), {}
        previous = ()
        # Each options save reloads the integration, including durable managers.
        for count, expected_requests in ((1, 1), (3, 3), (2, 3), (4, 4), (1, 4)):
            runtime = Runtime(core, stores, {UNIFORM: count})
            result = await runtime._batched_analysis()
            rows = result.recommendations
            assert len(rows) == count
            assert len(core.calls) == expected_requests
            assert tuple(row.numbers for row in rows[:len(previous)]) == previous[:count]
            assert [row.formula_game for row in rows] == list(range(1, count + 1))
            assert result.summary['game_shortfall'] == {}
            previous = tuple(row.numbers for row in rows)
        assert len(stores) == 4  # Shrinking sensors never deletes saved generation records.
    asyncio.run(scenario())


def test_mixed_formula_count_changes_keep_other_formulas_and_existing_games():
    async def scenario():
        core, stores = Core(), {}
        old = await Runtime(core, stores, {UNIFORM: 1, HOT: 3}, (UNIFORM, HOT))._batched_analysis()
        new = await Runtime(core, stores, {UNIFORM: 3, HOT: 2}, (UNIFORM, HOT))._batched_analysis()
        for key, count in ((UNIFORM, 1), (HOT, 2)):
            assert [r.numbers for r in new.recommendations_by_method(key)[:count]] == [
                r.numbers for r in old.recommendations_by_method(key)[:count]]
        assert len(new.recommendations) == 5
        assert new.summary['game_shortfall'] == {}
        assert core.calls[-1]['formula_ids'] == (UNIFORM,)
    asyncio.run(scenario())


def test_connection_recovery_fills_every_configured_slot_on_the_first_refresh():
    async def scenario():
        core = Core()
        runtime = Runtime(core, {}, {UNIFORM: 3}, disconnected=True)
        result = await runtime._batched_analysis()
        assert len(result.recommendations) == len(core.calls) == 3
        assert runtime.generator.client is core
    asyncio.run(scenario())


def test_reduced_count_trims_cached_multi_game_primary_result_without_a_request():
    async def scenario():
        core, stores = Core(), {}
        original = await Runtime(core, stores, {UNIFORM: 3})._batched_analysis()
        saved = stores[0].value['last_result']
        saved['games'] = [deepcopy(stores[index].value['last_result']['games'][0]) for index in range(3)]
        calls = len(core.calls)
        result = await Runtime(core, stores, {})._batched_analysis()
        assert len(result.recommendations) == 1
        assert result.recommendations[0].numbers == original.recommendations[0].numbers
        assert len(core.calls) == calls
        assert len(stores[0].value['last_result']['games']) == 3
    asyncio.run(scenario())


def test_completing_one_async_batch_starts_a_follower_for_the_next(monkeypatch):
    real_sleep = asyncio.sleep

    async def no_delay(_seconds):
        await real_sleep(0)

    monkeypatch.setattr(asyncio, 'sleep', no_delay)

    async def scenario():
        runtime = Runtime(Core(), {}, {UNIFORM: 3})
        scheduled = []
        refreshes = []

        class PendingManager:
            def __init__(self):
                self.polls = 0

            async def poll(self):
                self.polls += 1
                return SimpleNamespace(status='running' if self.polls <= 8 else 'completed')

        def create_task(coroutine, name):
            task = asyncio.create_task(coroutine, name=name)
            scheduled.append(task)
            return task

        runtime.hass = SimpleNamespace(async_create_task=create_task)

        async def refresh():
            refreshes.append(1)
            if len(refreshes) < 3:
                await runtime._finish_or_schedule(PendingManager(), SimpleNamespace(status='running'))

        runtime.owner.async_request_refresh = refresh
        await runtime._finish_or_schedule(PendingManager(), SimpleNamespace(status='running'))
        # Finite three-game request: each completion must schedule the next job.
        index = 0
        while index < len(scheduled):
            await scheduled[index]
            index += 1
        assert len(refreshes) == len(scheduled) == 3
        assert not runtime.retry_tasks
    asyncio.run(scenario())


def test_sensor_names_sort_by_formula_even_when_a_game_matches_a_purchase():
    labels = ('균등 공식 · Floyd', '빈도 프리셋 · 핫넘버')
    names = [entities.game_entity_name(n, label, purchased=(n == 2))
             for n in (1, 2, 3) for label in labels]
    assert [name.split(' | ')[0] for name in sorted(names)] == [labels[0]] * 3 + [labels[1]] * 3


def test_options_cleanup_and_startup_cleanup_happen_before_network_refresh():
    tree = ast.parse((BASE / '__init__.py').read_text(encoding='utf-8'))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.AsyncFunctionDef)}
    for name, later in (('_async_reload_entry', 'async_reload'),
                        ('async_setup_entry', 'async_config_entry_first_refresh')):
        calls = [node for node in ast.walk(functions[name]) if isinstance(node, ast.Call)]
        prune = next(node for node in calls if isinstance(node.func, ast.Name)
                     and node.func.id == '_prune_stale_optional_sensor_entities')
        network = next(node for node in calls if isinstance(node.func, ast.Attribute)
                       and node.func.attr == later)
        assert prune.lineno < network.lineno


def test_registry_cleanup_preserves_retained_custom_names_and_unrelated_entities():
    tree = ast.parse((BASE / 'sensor.py').read_text(encoding='utf-8'))
    wanted = {'_active_optional_sensor_unique_ids', '_prune_stale_optional_sensor_entities'}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in wanted]
    rows = [SimpleNamespace(
        entity_id=f'sensor.custom_{n}', unique_id=entities.game_unique_id('entry', UNIFORM, n),
        domain='sensor', platform='lotto_645', name=f'내 이름 {n}', disabled_by='user',
    ) for n in range(1, 4)]
    retained = rows[0]
    rows.extend([
        SimpleNamespace(entity_id='sensor.guide', unique_id='entry_method_guide', domain='sensor', platform='lotto_645'),
        SimpleNamespace(entity_id='sensor.other', unique_id='entry_method_other', domain='sensor', platform='other'),
        SimpleNamespace(entity_id='button.refresh', unique_id='entry_method_refresh', domain='button', platform='lotto_645'),
        SimpleNamespace(entity_id='sensor.purchase', unique_id='entry_purchased_tickets', domain='sensor', platform='lotto_645'),
    ])
    removed = []
    registry = SimpleNamespace(async_remove=removed.append)
    namespace = {
        'er': SimpleNamespace(async_get=lambda hass: registry,
                              async_entries_for_config_entry=lambda registry, entry_id: rows),
        'DOMAIN': 'lotto_645', 'configured_game_unique_ids': entities.configured_game_unique_ids,
        'METHOD_MYUNGRI_HETU': 'saju', 'HomeAssistant': object,
        'ConfigEntry': object, 'Lotto645Coordinator': object,
    }
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<sensor>', 'exec'), namespace)
    entry = SimpleNamespace(entry_id='entry', options={})
    owner = SimpleNamespace(entry=entry, configured_method_ids=(UNIFORM,),
                            selected_method_ids=(), ai_enabled=False, game_count=lambda key: 1)
    # No current data or active service is required, only the saved configuration.
    namespace['_prune_stale_optional_sensor_entities'](object(), entry, owner)
    assert removed == ['sensor.custom_2', 'sensor.custom_3']
    assert retained.entity_id == 'sensor.custom_1'
    assert retained.name == '내 이름 1' and retained.disabled_by == 'user'


def test_cleanup_keeps_configured_formula_ids_before_the_catalog_is_loaded():
    options = {'selected_methods': ['future_formula'], 'game_counts': {'future_formula': 3}}
    assert entities.configured_game_unique_ids('entry', options, ()) == {
        'entry_method_future_formula', 'entry_method_future_formula_g2', 'entry_method_future_formula_g3'}
