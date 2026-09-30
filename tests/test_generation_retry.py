"""Automatic recovery of interrupted remote generations (does not import Home Assistant)."""
import ast
import asyncio
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
import hashlib
import importlib
import json
from pathlib import Path
import sys
import time
import types
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'custom_components/lotto_645'
PACKAGE = 'lotto_generation_retry_test'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(BASE)]
sys.modules[PACKAGE] = package
remote = importlib.import_module(PACKAGE + '.remote_generation')
lab = importlib.import_module(PACKAGE + '.lab_client')
contract = importlib.import_module(PACKAGE + '.service_contract')

FID = 'uniform_fisher_yates'
NOW = datetime(2026, 9, 30, 4, 0, tzinfo=UTC)


class MemoryStore:
    def __init__(self, value=None):
        self.value = deepcopy(value)

    async def async_load(self):
        return deepcopy(self.value)

    async def async_save(self, value):
        self.value = deepcopy(value)


def failure(minutes_ago=None, attempts=1, context='ctx'):
    row = {'generation_id': 'gen-old', 'status': 'cancelled', 'context_tag': context}
    if minutes_ago is not None:
        row.update(failed_at=(NOW - timedelta(minutes=minutes_ago)).isoformat(), attempts=attempts)
    return row


def test_retry_due_backs_off_exponentially_and_caps_at_six_hours():
    assert remote.retry_due(None, NOW) is False
    assert remote.retry_due({}, NOW) is False
    assert remote.retry_due(failure(), NOW) is True  # pre-2.4.5 record without a timestamp
    assert remote.retry_due({**failure(), 'failed_at': 'not-a-date'}, NOW) is True
    assert remote.retry_due(failure(0), NOW) is False
    assert remote.retry_due(failure(9.9), NOW) is False
    assert remote.retry_due(failure(10), NOW) is True
    assert remote.retry_due(failure(39, attempts=3), NOW) is False
    assert remote.retry_due(failure(40, attempts=3), NOW) is True
    assert remote.retry_due(failure(359, attempts=50), NOW) is False
    assert remote.retry_due(failure(360, attempts=50), NOW) is True
    naive = {**failure(), 'failed_at': (NOW - timedelta(minutes=11)).replace(tzinfo=None).isoformat(), 'attempts': 1}
    assert remote.retry_due(naive, NOW) is True


def failed_generation(key, status='failed'):
    return contract.Generation.parse(
        {'contract_version': 1, 'generation_id': 'gen-' + status, 'request_key': key, 'status': status,
         'target_round': 31, 'based_on_round': 30, 'core_version': '1.25.0', 'results': []},
        expected_key=key, expected_target=31, requested_ids=(FID,))


def test_failure_record_is_timed_and_counts_attempts_per_context():
    class FailingClient:
        async def async_generate(self, **kwargs):
            return failed_generation(kwargs['request_key'], 'cancelled')

    async def scenario():
        store = MemoryStore()
        manager = remote.RemoteGeneration(FailingClient(), store)
        await manager.start(target_round=31, formula_ids=[FID], context_tag='ctx-a')
        first = store.value['last_failure']
        assert first['attempts'] == 1 and first['status'] == 'cancelled' and first['context_tag'] == 'ctx-a'
        assert datetime.fromisoformat(first['failed_at']).tzinfo is not None
        assert store.value['pending'] is None
        await manager.start(target_round=31, formula_ids=[FID], context_tag='ctx-a')
        assert store.value['last_failure']['attempts'] == 2
        await manager.start(target_round=31, formula_ids=[FID], context_tag='ctx-b')
        assert store.value['last_failure']['attempts'] == 1
    asyncio.run(scenario())


def test_discard_pending_keeps_the_last_result():
    async def scenario():
        store = MemoryStore({'schema': 1, 'pending': {'request_key': 'k', 'generation_id': 'lost'},
                             'last_result': {'generation_id': 'kept'}})
        await remote.RemoteGeneration(None, store).discard_pending()
        assert store.value['pending'] is None
        assert store.value['last_result'] == {'generation_id': 'kept'}
    asyncio.run(scenario())


def runtime_analysis():
    tree = ast.parse((BASE / 'service_runtime.py').read_text(encoding='utf-8'))
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.AsyncFunctionDef) and n.name == '_analysis')
    namespace = {'hashlib': hashlib, 'json': json, 'time': time, 'datetime': datetime, 'asdict': asdict,
                 'CONF_PERSONAL_CONSENT': 'personal_consent', 'METHOD_MYUNGRI_HETU': 'myungri_hetu_day_pillar',
                 'METHODS_BY_ID': {FID: SimpleNamespace(status='active')},
                 'LabServiceError': lab.LabServiceError, 'retry_due': remote.retry_due}
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<service_runtime>', 'exec'), namespace)
    return namespace['_analysis']


CONTEXT = hashlib.sha256(json.dumps([1244, [FID], 'material', 7]).encode()).hexdigest()


class Manager:
    def __init__(self, state, poll_error=None):
        self._state = {'schema': 1, 'pending': None, 'last_result': None, **state}
        self.poll_error = poll_error
        self.starts = []
        self.discarded = False

    async def state(self):
        return deepcopy(self._state)

    async def poll(self):
        raise lab.LabServiceError(self.poll_error)

    async def discard_pending(self):
        self.discarded = True
        self._state['pending'] = None

    async def start(self, **kwargs):
        self.starts.append(kwargs)
        return contract.Generation('gen-new', 'key', 'completed', 1244, 1243, '1.25.0',
                                   '2026-09-30T04:00:00+00:00', ())


class Runtime:
    _analysis = runtime_analysis()

    def __init__(self, manager):
        self.connection_manager = SimpleNamespace(needs_refresh=False)
        self.client = object()
        self.catalog = SimpleNamespace(core_version='1.25.0')
        self.catalog_updated_at = time.monotonic()
        self.status = 'ready'
        self.owner = SimpleNamespace(selected_method_ids=(FID,), history=[SimpleNamespace(round=1243)],
                                     saju_profile=None, _local_generation_nonce=7,
                                     _local_generated_at=None, _needs_storage_save=False)
        self.entry = SimpleNamespace(options={})
        self.generator = manager

    def material_context(self, options, profile):
        return 'material'

    async def prepare(self):
        raise AssertionError('connection is already prepared')

    async def _finish_or_schedule(self, manager, result):
        return result

    def _previous_analysis(self, state):
        return 'previous'

    def analysis_from_saved(self, saved, ids, nonce, status):
        return ('saved', saved['generation_id'], status)


def run(manager):
    runtime = Runtime(manager)
    return runtime, asyncio.run(runtime._analysis())


def test_pre_update_failure_for_the_same_request_is_retried_automatically():
    manager = Manager({'last_failure': failure(context=CONTEXT)})
    runtime, result = run(manager)
    assert result == ('saved', 'gen-new', 'ready') and runtime.status == 'ready'
    assert len(manager.starts) == 1 and manager.starts[0]['context_tag'] == CONTEXT


def test_fresh_failure_waits_for_backoff_instead_of_looping():
    fresh = {**failure(context=CONTEXT), 'failed_at': datetime.now(UTC).isoformat(), 'attempts': 1}
    manager = Manager({'last_failure': fresh})
    runtime, result = run(manager)
    assert result == 'previous' and runtime.status == 'cancelled' and manager.starts == []


def test_failure_older_than_backoff_is_retried():
    old = {**failure(context=CONTEXT), 'failed_at': (datetime.now(UTC) - timedelta(minutes=11)).isoformat(), 'attempts': 1}
    manager = Manager({'last_failure': old})
    runtime, result = run(manager)
    assert result == ('saved', 'gen-new', 'ready') and len(manager.starts) == 1


def test_job_unknown_to_the_service_is_discarded_and_regenerated():
    manager = Manager({'pending': {'generation_id': 'lost', 'request_key': 'k', 'context_tag': 'old'}}, 'not_found')
    runtime, result = run(manager)
    assert manager.discarded is True
    assert result == ('saved', 'gen-new', 'ready') and len(manager.starts) == 1


def test_unreachable_pending_job_is_kept_for_the_periodic_retry():
    manager = Manager({'pending': {'generation_id': 'gen-1', 'request_key': 'k', 'context_tag': CONTEXT}},
                      'connection_unavailable')
    runtime, result = run(manager)
    assert result == 'previous' and runtime.status == 'pending_recovery_required'
    assert manager.discarded is False and manager.starts == []


def test_periodic_retry_covers_pending_and_due_failures():
    source = (BASE / '__init__.py').read_text(encoding='utf-8')
    for status in ("'generating'", "'pending_recovery_required'", "{'failed', 'cancelled'}"):
        assert status in source, status
    assert 'await coordinator.service.generation_retry_due()' in source
