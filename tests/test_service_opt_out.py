"""The Lotto Lab service is disclosed at setup, stays on by default, and can be turned off."""
import ast
import asyncio
from datetime import UTC, datetime
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import voluptuous as vol

const = importlib.import_module('custom_components.lotto_645.const')
lab = importlib.import_module('custom_components.lotto_645.lab_client')

BASE = Path(__file__).resolve().parents[1] / 'custom_components/lotto_645'
TRANSLATIONS = [BASE / 'strings.json', BASE / 'translations/en.json', BASE / 'translations/ko.json']
KEY = const.CONF_USE_SERVICE


def _function(module, name, cls=None):
    tree = ast.parse((BASE / module).read_text(encoding='utf-8'))
    scope = tree.body
    if cls:
        scope = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls).body
    return next(n for n in scope
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)


def _compile(nodes, namespace):
    exec(compile(ast.Module(body=nodes, type_ignores=[]), '<lotto>', 'exec'), namespace)
    return namespace


SELECTOR = SimpleNamespace(BooleanSelector=lambda *a, **k: bool,
                           EntitySelector=lambda *a, **k: str,
                           EntitySelectorConfig=lambda **k: None)


class Flow:
    def __init__(self, entries=()):
        self.entries = list(entries)

    def _async_current_entries(self):
        return self.entries

    def async_abort(self, **kwargs):
        return {'type': 'abort', **kwargs}

    def async_show_form(self, **kwargs):
        return {'type': 'form', **kwargs}

    def async_create_entry(self, **kwargs):
        return {'type': 'create_entry', **kwargs}


def _user_step():
    namespace = _compile([_function('config_flow.py', 'async_step_user', 'Lotto645ConfigFlow')], {
        'vol': vol, 'selector': SELECTOR, 'NAME': const.NAME,
        'CONF_USE_SERVICE': KEY, 'DEFAULT_USE_SERVICE': const.DEFAULT_USE_SERVICE,
    })
    return namespace['async_step_user']


def test_service_stays_on_by_default():
    assert const.DEFAULT_USE_SERVICE is True


def test_setup_shows_the_disclosure_form_before_creating_the_entry():
    form = asyncio.run(_user_step()(Flow()))
    assert form['type'] == 'form' and form['step_id'] == 'user'
    # Submitting the untouched form keeps the automatic connection on.
    assert form['data_schema']({}) == {KEY: True}


def test_default_setup_keeps_existing_entry_shape_and_off_is_stored():
    step = _user_step()
    created = asyncio.run(step(Flow(), {KEY: True}))
    assert created['type'] == 'create_entry'
    assert created['data'] == {} and created['options'] == {}
    off = asyncio.run(step(Flow(), {KEY: False}))
    assert off['options'] == {KEY: False}
    assert asyncio.run(step(Flow(['existing'])))['reason'] == 'single_instance_allowed'


def test_setup_text_names_the_service_and_what_it_receives():
    for path in TRANSLATIONS:
        data = json.loads(path.read_text(encoding='utf-8'))
        user = data['config']['step']['user']
        assert 'lotto.formulab.kr' in user['description'], path.name
        assert user['data'][KEY] and user['data_description'][KEY], path.name
        recommendations = data['options']['step']['recommendations']
        assert recommendations['data'][KEY] and recommendations['data_description'][KEY], path.name
        assert data['options']['abort']['service_disabled'], path.name


def test_setup_text_names_every_background_request():
    # Not only the 5-minute check: renewal, catalog re-read and job polling too.
    phrases = {
        'en': ('status check every 5 minutes', 'renews the registration before its credential expires',
               'formula list about once an hour', 'polls running generation jobs', 'final computation'),
        'ko': ('5분마다 연결 상태 확인', '만료되기 전에 등록을 갱신', '약 1시간마다 공식 목록',
               '생성 중인 작업은 끝날 때까지', '최종 산출'),
    }
    for path in TRANSLATIONS:
        description = json.loads(path.read_text(encoding='utf-8'))['config']['step']['user']['description']
        for phrase in phrases['ko' if path.name == 'ko.json' else 'en']:
            assert phrase in description, (path.name, phrase)
    readme = (BASE.parents[1] / 'README.md').read_text(encoding='utf-8')
    for phrase in ('등록을 자동 갱신', '1시간이 지났으면 공식 목록', '끝날 때까지 상태를 확인',
                   '갱신할 때마다 준비 상태', '`connection_type` 속성이 `사용 안 함`'):
        assert phrase in readme, phrase


def _runtime(options):
    class Store:
        async def async_load(self):
            return None

    class Manager:
        def __init__(self):
            self.calls = []
            self.values = {}

        async def load(self, legacy=None):
            self.calls.append('load')

        async def ensure_enrolled(self, session):
            self.calls.append('enroll')
            raise lab.LabServiceError('connection_unavailable')

    namespace = _compile([
        _function('service_runtime.py', 'prepare', 'ServiceRuntime'),
        _function('service_runtime.py', '_record_health', 'ServiceRuntime'),
    ], {
        'datetime': datetime, 'UTC': UTC, 'LabServiceError': lab.LabServiceError,
        'without_user_connection': dict, 'async_get_clientsession': lambda hass: 'session',
        'CONF_USE_SERVICE': KEY, 'DEFAULT_USE_SERVICE': const.DEFAULT_USE_SERVICE,
    })
    runtime = SimpleNamespace(
        catalog=None, catalog_store=Store(), client=None, status='not_connected', health={},
        connection_manager=Manager(), entry=SimpleNamespace(data={}, options=options),
        hass=SimpleNamespace(config_entries=SimpleNamespace(async_update_entry=None)),
    )
    runtime._record_health = namespace['_record_health'].__get__(runtime)
    runtime.prepare = namespace['prepare'].__get__(runtime)
    return runtime


def test_turned_off_service_creates_no_identity_and_sends_nothing():
    runtime = _runtime({KEY: False})
    asyncio.run(runtime.prepare())
    assert runtime.connection_manager.calls == []
    assert runtime.client is None and runtime.status == 'service_disabled'
    assert runtime.health['ok'] is False and runtime.health['error'] == 'service_disabled'


def test_existing_and_default_entries_still_enroll_automatically():
    for options in ({}, {KEY: True}):
        runtime = _runtime(options)
        asyncio.run(runtime.prepare())
        assert runtime.connection_manager.calls == ['load', 'enroll']
        assert runtime.status == 'connection_unavailable'


def test_member_link_menu_does_not_contact_a_turned_off_service():
    namespace = _compile([_function('config_flow.py', 'async_step_account', 'Lotto645OptionsFlow')], {
        'Any': object, 'ConfigFlowResult': object,
        'CONF_USE_SERVICE': KEY, 'DEFAULT_USE_SERVICE': const.DEFAULT_USE_SERVICE,
    })
    flow = SimpleNamespace(_options={KEY: False},
                           async_abort=lambda **kwargs: {'type': 'abort', **kwargs})
    result = asyncio.run(namespace['async_step_account'](flow))
    assert result == {'type': 'abort', 'reason': 'service_disabled'}


def _recommendation_schema():
    nodes = [_function('config_flow.py', name)
             for name in ('_optional_text_marker', '_recommendation_schema')]
    namespace = _compile(nodes, {
        'vol': vol, 'selector': SELECTOR, 'Any': object,
        'normalize_method_ids': lambda ids: tuple(dict.fromkeys(ids)),
        'DEFAULT_METHOD_IDS': ('hot_numbers',), 'ADVANCED_METHOD_IDS': frozenset(),
        '_method_selector': lambda **kwargs: list,
        **{name: getattr(const, name) for name in dir(const) if name.isupper()},
    })
    return namespace['_recommendation_schema']


def test_options_show_the_current_service_choice():
    build = _recommendation_schema()
    for options, expected in (({}, True), ({KEY: True}, True), ({KEY: False}, False)):
        marker = next(key for key in build(options).schema if str(key) == KEY)
        assert marker.default() is expected
