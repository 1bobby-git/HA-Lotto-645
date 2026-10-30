"""Recorder history and diagnostics never keep purchased numbers or credentials."""
import ast
import asyncio
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

const = importlib.import_module('custom_components.lotto_645.const')
BASE = Path(__file__).resolve().parents[1] / 'custom_components/lotto_645'


def _class_constant(module, cls_name, name):
    tree = ast.parse((BASE / module).read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls_name)
    for node in cls.body:
        if isinstance(node, ast.Assign) and any(getattr(t, 'id', None) == name for t in node.targets):
            return ast.literal_eval(node.value.args[0])
    raise AssertionError(f'{cls_name}.{name} is not set')


def test_purchased_ticket_numbers_are_not_written_to_the_recorder():
    # The live state keeps every attribute for templates; only history skips the lines.
    assert 'games' in _class_constant('sensor.py', 'LottoPurchasedTicketsSensor', '_unrecorded_attributes')


SECRET_TOKEN = 'secret-token-value-0123456789'
BIRTH_DATE = '1982-03-15'
TICKET = [3, 11, 19, 27, 35, 43]


def _entry(loaded=True):
    options = {
        const.CONF_SELECTED_METHODS: ['hot_numbers'],
        const.CONF_GAME_COUNTS: {'hot_numbers': 2},
        const.CONF_SAJU_BIRTH_DATE: BIRTH_DATE,
        const.CONF_SAJU_BIRTH_TIME: '14:30',
        const.CONF_SAJU_BIRTH_PLACE: '서울특별시',
        const.CONF_PERSONAL_CONSENT: True,
    }
    entry = SimpleNamespace(entry_id='entry', data={}, options=options)
    if not loaded:
        return entry
    connection = SimpleNamespace(state={
        'source': 'automatic', 'installation_id': 'a' * 32,
        'credentials': {const.CONF_SERVICE_URL: 'https://lotto.formulab.kr',
                        const.CONF_SERVICE_TOKEN: SECRET_TOKEN},
    })
    service = SimpleNamespace(
        status='ready', connection_manager=connection,
        health={'ok': True, 'error': None, 'since': '2026-10-24T12:00:00+00:00',
                'latest_round': 1195, 'core_version': '1.25.0', 'token': SECRET_TOKEN},
        catalog=SimpleNamespace(core_version='1.25.0'),
        info={'device_id': 'ha-' + 'a' * 32},
    )
    analysis = SimpleNamespace(target_round=1196, recommendations=[SimpleNamespace(numbers=tuple(TICKET))] * 2,
                               summary={'game_shortfall': {}})
    data = SimpleNamespace(analysis=analysis, source_status='shared_mirror', ai_status='disabled')
    book = SimpleNamespace(tickets={'t1': {'round': 1196, 'games': [{'slot': 'A', 'numbers': TICKET}]}})
    entry.runtime_data = SimpleNamespace(
        service=service, data=data, history=[SimpleNamespace(round=n) for n in range(1, 1196)],
        purchase_book=book, purchase_storage_error=False, review_storage_error=False,
    )
    return entry


def test_diagnostics_keep_operational_state_only():
    diagnostics = importlib.import_module('custom_components.lotto_645.diagnostics')
    result = asyncio.run(diagnostics.async_get_config_entry_diagnostics(None, _entry()))
    text = json.dumps(result, ensure_ascii=False)
    for private in (SECRET_TOKEN, BIRTH_DATE, '14:30', '서울특별시', 'a' * 32, '3, 11, 19'):
        assert private not in text
    assert ', '.join(map(str, TICKET)) not in text and str(TICKET) not in text
    assert result['version'] == const.VERSION and result['loaded'] is True
    assert result['service']['status'] == 'ready' and result['service']['connection_type'] == 'automatic'
    assert result['service']['health']['latest_round'] == 1195
    assert result['history'] == {'latest_round': 1195, 'draw_count': 1195, 'source_status': 'shared_mirror'}
    assert result['recommendations']['game_count'] == 2
    assert result['purchases'] == {'ticket_count': 1, 'storage_error': False}
    assert result['options']['saju_profile_saved'] is True
    assert result['options']['use_lotto_lab_service'] is True


def test_diagnostics_work_before_the_entry_is_loaded():
    diagnostics = importlib.import_module('custom_components.lotto_645.diagnostics')
    result = asyncio.run(diagnostics.async_get_config_entry_diagnostics(None, _entry(loaded=False)))
    assert result['loaded'] is False and BIRTH_DATE not in json.dumps(result)
