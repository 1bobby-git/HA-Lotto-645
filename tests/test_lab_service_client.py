"""Focused public transport checks. This file does not import HA or Core."""
import asyncio
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import types

import aiohttp
from aiohttp import web
import pytest

BASE = Path(__file__).resolve().parents[1] / 'custom_components/lotto_645'
PACKAGE = 'lotto_public_client_test'
package = types.ModuleType(PACKAGE)
package.__path__ = [str(BASE)]
sys.modules[PACKAGE] = package
from lotto_public_client_test.lab_client import LottoLabClient, LabServiceError, service_origin
from lotto_public_client_test.service_contract import Generation, ContractError, Catalog

KEY = 'req-12345678'
FID = 'uniform_fisher_yates'
TOKEN = 'test-scoped-token-not-a-github-token'


def payload():
    return {'contract_version': 1, 'generation_id': 'gen-1', 'request_key': KEY, 'status': 'completed',
            'target_round': 31, 'based_on_round': 30, 'core_version': '1.22.0',
            'generated_at': '2026-09-16T06:00:00+00:00',
            'results': [{'formula_id': FID, 'formula_version': '1', 'name': '균등 생성',
                         'category': '균등', 'status': 'generated', 'numbers': [1, 2, 3, 4, 5, 6],
                         'public_reason': '선택한 공개 설정으로 생성', 'reason_code': None}]}


def parse(raw):
    return Generation.parse(raw, expected_key=KEY, expected_target=31, requested_ids=(FID,))


def test_safe_projection_discards_server_internal_fields():
    raw = payload(); raw['private'] = 'canary'; raw['results'][0]['weights'] = 'canary'
    result = parse(raw)
    assert result.games[0].numbers == (1, 2, 3, 4, 5, 6)
    assert 'canary' not in repr(result)


@pytest.mark.parametrize('mutate', [
    lambda r: r.update(request_key='wrong-key'),
    lambda r: r.update(target_round=32),
    lambda r: r.update(generated_at='2026-09-16T00:00:00'),
    lambda r: r.update(status='running'),
    lambda r: r['results'][0].update(numbers=[True, 2, 3, 4, 5, 6]),
    lambda r: r['results'][0].update(numbers=[1, 1, 3, 4, 5, 6]),
    lambda r: r['results'].clear(),
])
def test_context_and_output_rejected(mutate):
    raw = payload(); mutate(raw)
    with pytest.raises(ContractError): parse(raw)


def test_http_is_only_opt_in_loopback():
    with pytest.raises(ValueError): service_origin('http://127.0.0.1:1234')
    assert service_origin('http://127.0.0.1:1234', allow_loopback_http=True).endswith(':1234')
    for url in ['http://example.com', 'https://u:p@example.com', 'https://example.com?token=x', 'https://example.com/path']:
        with pytest.raises(ValueError): service_origin(url, allow_loopback_http=True)


async def with_server(handler, action):
    app = web.Application()
    app.router.add_route('*', '/{tail:.*}', handler)
    runner = web.AppRunner(app); await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0); await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        async with aiohttp.ClientSession() as session:
            client = LottoLabClient(session, f'http://127.0.0.1:{port}', TOKEN, allow_loopback_http=True)
            await action(client)
    finally:
        await runner.cleanup()


def test_request_and_retrieval_same_key_and_generation():
    seen = []
    async def handler(request):
        assert request.headers['Authorization'] == 'Bearer ' + TOKEN
        if request.method == 'POST':
            data = await request.json(); seen.append((data['request_key'], request.headers['Idempotency-Key']))
        return web.json_response(payload())
    async def action(client):
        created = await client.async_generate(request_key=KEY, target_round=31, formula_ids=[FID])
        fetched = await client.async_get_generation(created.generation_id, request_key=KEY, target_round=31, formula_ids=[FID])
        assert fetched == created
    asyncio.run(with_server(handler, action))
    assert seen == [(KEY, KEY)]


@pytest.mark.parametrize(('status', 'expected'), [(401, 'reauth_required'), (403, 'permission_denied'),
                                                (409, 'request_conflict'), (429, 'usage_limited'), (503, 'service_unavailable')])
def test_safe_status_errors(status, expected):
    async def handler(request):
        return web.Response(status=status, text='private traceback must not be exposed', headers={'Retry-After':'7'})
    async def action(client):
        with pytest.raises(LabServiceError) as error:
            await client.async_catalog()
        assert str(error.value) == expected
        assert 'private' not in str(error.value)
    asyncio.run(with_server(handler, action))


def test_redirect_does_not_forward_bearer_token():
    calls = []
    async def handler(request):
        calls.append(request.path)
        raise web.HTTPFound('/stolen-token')
    async def action(client):
        with pytest.raises(LabServiceError, match='redirect_refused'):
            await client.async_catalog()
    asyncio.run(with_server(handler, action))
    assert calls == ['/v1/formulas']


def test_profile_without_consent_sends_nothing():
    seen = []
    async def handler(request):
        seen.append(1); return web.json_response(payload())
    async def action(client):
        with pytest.raises(LabServiceError, match='personal_consent_required'):
            await client.async_generate(request_key=KEY, target_round=31, formula_ids=[FID], personal_profile={'private': 'x'})
    asyncio.run(with_server(handler, action))
    assert not seen


def test_durable_retry_uses_same_key_after_timeout():
    from lotto_public_client_test.remote_generation import RemoteGeneration
    class MemoryStore:
        value = None
        async def async_load(self): return deepcopy(self.value)
        async def async_save(self, value): self.value = deepcopy(value)
    class InterruptedClient:
        keys = []
        async def async_get_by_key(self, **kwargs):
            raise LabServiceError('not_found')
        async def async_generate(self, **kwargs):
            self.keys.append(kwargs['request_key'])
            if len(self.keys) == 1:
                raise LabServiceError('connection_unavailable')
            raw = payload(); raw['request_key'] = kwargs['request_key']
            return Generation.parse(raw, expected_key=kwargs['request_key'], expected_target=31, requested_ids=(FID,))
    async def scenario():
        store, client = MemoryStore(), InterruptedClient()
        first = RemoteGeneration(client, store)
        with pytest.raises(LabServiceError):
            await first.start(target_round=31, formula_ids=[FID])
        assert store.value['pending'] is not None
        restarted = RemoteGeneration(client, store)
        result = await restarted.start(target_round=31, formula_ids=[FID])
        assert client.keys[0] == client.keys[1]
        assert store.value['pending'] is None
        assert (await restarted.saved_result())['generation_id'] == result.generation_id
    asyncio.run(scenario())


def test_storage_error_does_not_start_request():
    from lotto_public_client_test.remote_generation import RemoteGeneration
    class FailingStore:
        async def async_load(self): return None
        async def async_save(self, value): raise OSError('disk full')
    class NoCall:
        async def async_generate(self, **kwargs): raise AssertionError('POST before durable reservation')
    async def scenario():
        with pytest.raises(OSError):
            await RemoteGeneration(NoCall(), FailingStore()).start(target_round=31, formula_ids=[FID])
    asyncio.run(scenario())
