"""A turned-off Lotto Lab service: the real runtime sends nothing and is not shown as a fault."""
import ast
import asyncio
from datetime import datetime
import importlib
from pathlib import Path
import shutil
import subprocess
import sys
import types
from types import SimpleNamespace

import pytest

const = importlib.import_module('custom_components.lotto_645.const')
lab = importlib.import_module('custom_components.lotto_645.lab_client')
models = importlib.import_module('custom_components.lotto_645.models')

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'custom_components/lotto_645'
KEY = const.CONF_USE_SERVICE


class RecordingSession:
    """Any use of the shared aiohttp session counts as a network call."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, attr):
        def call(*args, **kwargs):
            self.calls.append(attr)
            raise AssertionError(f'network call {attr} {args[:1]}')
        return call


class MemoryStore:
    data = {}
    saved = []

    def __init__(self, hass, version, key):
        self.key = key

    async def async_load(self):
        return MemoryStore.data.get(self.key)

    async def async_save(self, data):
        MemoryStore.saved.append(self.key)
        MemoryStore.data[self.key] = data


@pytest.fixture
def runtime_module(monkeypatch):
    """Import the real service_runtime with only HA's session and Store replaced."""
    before = set(sys.modules)
    ha = types.ModuleType('homeassistant')
    ha.__path__ = []
    helpers = types.ModuleType('homeassistant.helpers')
    helpers.__path__ = []
    aio = types.ModuleType('homeassistant.helpers.aiohttp_client')
    aio.async_get_clientsession = lambda hass: None
    storage = types.ModuleType('homeassistant.helpers.storage')
    storage.Store = MemoryStore
    for name, module in {
        'homeassistant': ha, 'homeassistant.helpers': helpers,
        'homeassistant.helpers.aiohttp_client': aio, 'homeassistant.helpers.storage': storage,
    }.items():
        monkeypatch.setitem(sys.modules, name, module)
    module = importlib.import_module('custom_components.lotto_645.service_runtime')
    session = RecordingSession()
    monkeypatch.setattr(module, 'async_get_clientsession', lambda hass: session)
    monkeypatch.setattr(module, 'Store', MemoryStore)
    MemoryStore.data, MemoryStore.saved = {}, []
    module.session_under_test = session
    yield module
    for name in set(sys.modules) - before:
        if name.startswith('custom_components.lotto_645.'):
            sys.modules.pop(name, None)


def _runtime(module, options):
    def no_task(coro, name=None):
        coro.close()
        raise AssertionError(f'unexpected background task {name}')

    hass = SimpleNamespace(
        async_create_task=no_task, async_create_background_task=no_task,
        config_entries=SimpleNamespace(async_update_entry=lambda *a, **k: None,
                                       async_reload=lambda entry_id: None),
    )
    entry = SimpleNamespace(entry_id='entry1', data={}, options=dict(options))
    history = [models.LottoDraw(i, '2026-01-01', (1, 2, 3, 4, 5, 6), 7) for i in range(1, 1201)]

    async def refresh():
        return None

    owner = SimpleNamespace(
        hass=hass, entry=entry, history=history,
        selected_method_ids=('hot_numbers',), configured_method_ids=('hot_numbers',),
        formula_game_counts={'hot_numbers': 2}, _prediction_snapshot={'target_round': 1201, 'recommendations': []},
        _local_generation_nonce=0, saju_profile=None, _local_generated_at=None,
        _needs_storage_save=False, async_update_listeners=lambda: None, async_request_refresh=refresh,
    )
    return module.ServiceRuntime(owner)


ENROLLED = {
    'lotto_645.connection.entry1': {
        'version': 1, 'source': 'automatic', 'installation_id': 'a' * 32,
        'credentials': {'service_url': 'https://lotto.formulab.kr',
                        'service_token': 'x' * 43, 'service_certificate_sha256': ''},
        'enrolled': True, 'expires_at': 4102444800.0,
    }
}


@pytest.mark.parametrize('preset', [{}, ENROLLED], ids=['fresh_install', 'enrolled_install'])
def test_every_service_path_sends_nothing_while_the_service_is_off(runtime_module, preset):
    MemoryStore.data.update({key: dict(value) for key, value in preset.items()})
    runtime = _runtime(runtime_module, {KEY: False})

    async def exercise():
        await runtime.prepare()
        analysis = await runtime.analysis()
        healthy = await runtime.health_check()
        with pytest.raises(lab.LabServiceError) as ai_error:
            await runtime.ai_ticket(1201)
        with pytest.raises(lab.LabServiceError) as final_error:
            await runtime.finalization_state()
        retry_due = await runtime.generation_retry_due()
        await runtime.close()
        return analysis, healthy, ai_error.value.code, final_error.value.code, retry_due

    analysis, healthy, ai_code, final_code, retry_due = asyncio.run(exercise())
    assert runtime_module.session_under_test.calls == []
    assert MemoryStore.saved == []  # no installation identity or job state is written
    assert MemoryStore.data == preset  # an existing connection is kept for turning it back on
    assert runtime.client is None and runtime.status == 'service_disabled'
    assert analysis.target_round == 1201 and analysis.recommendations == ()
    assert analysis.summary['service_status'] == 'service_disabled'
    assert healthy is False and runtime.health['error'] == 'service_disabled'
    assert ai_code == 'not_connected' and final_code == 'finalization_not_supported'
    assert retry_due is False


def test_the_same_runtime_reaches_the_service_when_the_option_is_on(runtime_module):
    # Proves the recording session above would notice a request.
    runtime = _runtime(runtime_module, {})
    with pytest.raises(AssertionError, match='network call'):
        asyncio.run(runtime.prepare())
    assert runtime_module.session_under_test.calls


def _coordinator_function(name):
    tree = ast.parse((BASE / 'coordinator.py').read_text(encoding='utf-8'))
    return next(n for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


class HomeAssistantError(Exception):
    pass


class AiRecommendationError(HomeAssistantError):
    pass


def _auto_ai_block():
    """The AI auto-generation step of `_async_update_data`, run on its own."""
    method = _coordinator_function('_async_update_data')
    block = next(n for n in method.body
                 if isinstance(n, ast.If) and 'ai_auto_generate' in ast.unparse(n.test))
    function = ast.parse(
        'async def auto(self, analysis, ai_recommendation, suppress_ai_generation):\n'
        '    ai_status = "idle"\n    ai_error = None\n    ai_generated_at = None\n'
        '    return ai_status, ai_error'
    ).body[0]
    function.body.insert(3, block)
    warnings = []
    namespace = {
        'datetime': datetime, 'AiRecommendationError': AiRecommendationError,
        'HomeAssistantError': HomeAssistantError,
        '_LOGGER': SimpleNamespace(warning=lambda *args: warnings.append(args)),
    }
    exec(compile(ast.fix_missing_locations(ast.Module(body=[function], type_ignores=[])),
                 '<coordinator>', 'exec'), namespace)
    return namespace['auto'], warnings


def _coordinator(service_enabled):
    calls = []

    async def create(analysis, entity_id):
        calls.append(analysis)
        raise AiRecommendationError('not_connected')  # what ai_ticket() gives without a client

    return SimpleNamespace(ai_enabled=True, ai_auto_generate=True, service_enabled=service_enabled,
                           configured_ai_entity_id=None, _async_create_ai_recommendation=create), calls


def test_ai_auto_generation_is_skipped_quietly_while_the_service_is_off():
    auto, warnings = _auto_ai_block()
    coordinator, calls = _coordinator(service_enabled=False)
    assert asyncio.run(auto(coordinator, 'analysis', None, False)) == ('idle', None)
    assert calls == [] and warnings == []
    # With the service on, a failure is still reported as before.
    coordinator, calls = _coordinator(service_enabled=True)
    assert asyncio.run(auto(coordinator, 'analysis', None, False)) == ('error', 'not_connected')
    assert calls == ['analysis'] and len(warnings) == 1


def test_service_enabled_follows_the_option_and_defaults_to_on():
    namespace = {'CONF_USE_SERVICE': KEY, 'DEFAULT_USE_SERVICE': const.DEFAULT_USE_SERVICE}
    exec(compile(ast.Module(body=[_coordinator_function('service_enabled')], type_ignores=[]),
                 '<coordinator>', 'exec'), namespace)
    read = namespace['service_enabled'].fget
    for options, expected in (({}, True), ({KEY: True}, True), ({KEY: False}, False)):
        assert read(SimpleNamespace(entry=SimpleNamespace(options=options))) is expected


def test_manual_ai_request_explains_how_to_turn_the_service_back_on():
    namespace = {'AiRecommendationError': AiRecommendationError, 'Recommendation': object}
    exec(compile(ast.Module(body=[_coordinator_function('async_generate_ai_recommendation')],
                            type_ignores=[]), '<coordinator>', 'exec'), namespace)
    coordinator = SimpleNamespace(ai_enabled=True, service_enabled=False, data='unchanged')
    with pytest.raises(AiRecommendationError, match='추첨 공식 · AI · 데이터 소스') as error:
        asyncio.run(namespace['async_generate_ai_recommendation'](coordinator))
    assert 'not_connected' not in str(error.value)
    assert coordinator.data == 'unchanged'  # the AI status is not switched to "error"


def test_panel_explains_a_turned_off_service_instead_of_a_fault():
    core = (BASE / 'www/lotto-panel-core.js').read_text(encoding='utf-8')
    assert 'currentRecommendationText(serviceStatus)' in core
    assert 'serviceText.empty' in core and 'serviceText.note' in core
    if not shutil.which('node'):
        pytest.skip('Node unavailable; panel text contract not run')
    result = subprocess.run(['node', 'tests/js/service-disabled-view.mjs'], cwd=ROOT,
                            capture_output=True, text=True, encoding='utf-8', timeout=10)
    assert result.returncode == 0, result.stderr
