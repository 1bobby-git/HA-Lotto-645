"""Lotto Lab connection health check and background member-link completion (no HA import)."""
import ast
import asyncio
from datetime import UTC, datetime
import importlib
from pathlib import Path
import sys
import time
import types
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'custom_components/lotto_645'
PACKAGE = 'lotto_service_connection_test'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(BASE)]
sys.modules[PACKAGE] = package
lab = importlib.import_module(PACKAGE + '.lab_client')
LabServiceError = lab.LabServiceError


def methods(*names):
    tree = ast.parse((BASE / 'service_runtime.py').read_text(encoding='utf-8'))
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names]


def build(namespace, *names):
    exec(compile(ast.Module(body=methods(*names), type_ignores=[]), '<service_runtime>', 'exec'), namespace)
    return {name: namespace[name] for name in names}


class Manager:
    def __init__(self, needs_refresh=False):
        self.needs_refresh = needs_refresh
        self.values = {'service_token': 'x' * 32}
        self.invalidated = False
        self.enrolled = 0
        self.state = {'source': 'automatic'}
        self.saved = None
        self.store = SimpleNamespace(async_save=self._save)

    async def ensure_enrolled(self, session):
        self.enrolled += 1

    def invalidate(self):
        self.invalidated = True

    async def _save(self, value):
        self.saved = value


HEALTH = build({'datetime': datetime, 'UTC': UTC, 'LabServiceError': LabServiceError,
                'async_get_clientsession': lambda hass: 'session'}, '_record_health', 'health_check')


class Runtime:
    _record_health = HEALTH['_record_health']
    health_check = HEALTH['health_check']

    def __init__(self, client, status='ready', needs_refresh=False):
        self.lock = asyncio.Lock()
        self.client = client
        self.status = status
        self.health = {}
        self.info = {}
        self.hass = None
        self.connection_manager = Manager(needs_refresh)
        self.configured = 0

    def _configure_connection(self, values):
        self.configured += 1


class Client:
    def __init__(self, outcome):
        self.outcome = outcome
        self.calls = 0

    async def async_service_info(self):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


INFO = {'contract_version': 1, 'core_version': '1.25.0', 'device_id': 'ha-abc', 'latest_round': 1243}


def test_successful_health_check_reports_connected_and_keeps_since_stable():
    runtime = Runtime(Client(INFO))
    assert asyncio.run(runtime.health_check()) is True
    assert runtime.health['ok'] is True and runtime.health['error'] is None
    assert runtime.health['latest_round'] == 1243 and runtime.info['device_id'] == 'ha-abc'
    since = runtime.health['since']
    assert asyncio.run(runtime.health_check()) is True
    assert runtime.health['since'] == since  # no attribute churn between identical checks


def test_unreachable_service_marks_disconnected_and_flags_ready_status():
    runtime = Runtime(Client(LabServiceError('connection_unavailable')))
    runtime._record_health(True, INFO)
    assert asyncio.run(runtime.health_check()) is False
    assert runtime.health['ok'] is False and runtime.health['error'] == 'connection_unavailable'
    assert runtime.health['latest_round'] == 1243  # last known value is kept
    assert runtime.status == 'connection_unavailable'


def test_rejected_credential_requests_reauthentication():
    runtime = Runtime(Client(LabServiceError('reauth_required')))
    assert asyncio.run(runtime.health_check()) is False
    assert runtime.status == 'reauth_required' and runtime.connection_manager.invalidated is True


def test_expiring_credential_is_refreshed_before_the_check():
    runtime = Runtime(Client(INFO), needs_refresh=True)
    assert asyncio.run(runtime.health_check()) is True
    assert runtime.connection_manager.enrolled == 1 and runtime.configured == 1


def test_not_connected_runtime_reports_disconnected_without_a_request():
    runtime = Runtime(None, status='not_connected')
    assert asyncio.run(runtime.health_check()) is False
    assert runtime.health == {**runtime.health, 'ok': False, 'error': 'not_connected'}


TOKENS = {'access_token': 'a' * 43, 'refresh_token': 'b' * 64, 'device_id': 'c' * 32, 'expires_in': 900}


def link_runtime(outcomes):
    calls = []

    async def poll(session, grant):
        calls.append(grant['user_code'])
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    async def no_sleep(_seconds):
        return None

    namespace = {'asyncio': SimpleNamespace(sleep=no_sleep), 'time': time, 'LabServiceError': LabServiceError,
                 'async_get_clientsession': lambda hass: 'session', 'poll_member_link': poll,
                 'state_from_tokens': lambda tokens, previous: {'source': 'member', 'device_id': tokens['device_id']}}
    complete = build(namespace, '_complete_member_link')['_complete_member_link']
    reloads, tasks, updates = [], [], []

    class Hass:
        config_entries = SimpleNamespace(async_reload=lambda entry_id: reloads.append(entry_id) or 'reload')

        def async_create_task(self, target):
            tasks.append(target)

    runtime = SimpleNamespace(hass=Hass(), entry=SimpleNamespace(entry_id='entry'),
                              owner=SimpleNamespace(async_update_listeners=lambda: updates.append(1)),
                              connection_manager=Manager())
    link = {'grant': {'user_code': 'TYHT-X5DP', 'next_poll': 0}, 'status': 'pending'}
    return runtime, link, complete, calls, reloads, tasks


def test_approved_link_is_saved_and_the_entry_reloads_without_user_confirmation():
    runtime, link, complete, calls, reloads, tasks = link_runtime([
        LabServiceError('authorization_pending'), LabServiceError('member_service_unavailable'),
        LabServiceError('slow_down'), TOKENS])
    asyncio.run(complete(runtime, link))
    assert len(calls) == 4 and link['status'] == 'linked'
    assert runtime.connection_manager.saved == {'source': 'member', 'device_id': 'c' * 32}
    assert reloads == ['entry'] and tasks == ['reload']


def test_denied_or_expired_link_stops_without_saving():
    for code in ('access_denied', 'expired_token', 'device_limit'):
        runtime, link, complete, calls, reloads, tasks = link_runtime([LabServiceError(code)])
        asyncio.run(complete(runtime, link))
        assert link['status'] == code and runtime.connection_manager.saved is None and reloads == []


def test_connectivity_entity_and_periodic_health_check_are_wired():
    binary = (BASE / 'binary_sensor.py').read_text(encoding='utf-8')
    assert 'BinarySensorDeviceClass.CONNECTIVITY' in binary and "_service_connection'" in binary
    assert 'EntityCategory.DIAGNOSTIC' in binary and "'회원 계정 연결'" in binary
    assert 'LottoServiceConnectionSensor(entry.runtime_data)' in binary
    init = (BASE / '__init__.py').read_text(encoding='utf-8')
    assert init.index('await coordinator.service.health_check()') < init.index('status = coordinator.service.status')
    flow = (BASE / 'config_flow.py').read_text(encoding='utf-8')
    assert 'service.watch_member_link(grant)' in flow
    assert 'link.get("grant") is grant' in flow and 'tokens = await poll_member_link(session, grant)' in flow
