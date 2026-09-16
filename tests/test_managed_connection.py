"""Focused tests for managed connection, preserved journals and removed UI."""
import asyncio
import ast
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from custom_components.lotto_645.managed_connection import ManagedConnection, connection_values, without_user_connection
from custom_components.lotto_645.lab_client import LabServiceError
from custom_components.lotto_645.const import CONF_SERVICE_URL as URL, CONF_SERVICE_TOKEN as TOKEN, CONF_SERVICE_CERT as CERT
R=Path(__file__).resolve().parents[1]/'custom_components/lotto_645'

class MemoryStore:
    def __init__(self, value=None, fail=False):self.value=value;self.fail=fail;self.writes=0
    async def async_load(self):return copy.deepcopy(self.value)
    async def async_save(self, value):
        if self.fail:raise OSError('disk unavailable')
        self.value=copy.deepcopy(value);self.writes+=1

class Response:
    status=201;content_type='application/json'
    def __init__(self, iid, status=201):self.iid=iid;self.status=status;self.content=self
    async def __aenter__(self):return self
    async def __aexit__(self,*args):pass
    async def iter_chunked(self,n):
        yield json.dumps({'contract_version':1,'installation_id':self.iid,'enrolled':True}).encode()

class Session:
    def __init__(self, status=201):self.calls=[];self.status=status
    def post(self,url,**kwargs):
        self.calls.append((url,kwargs))
        return Response(kwargs['json']['installation_id'],self.status)

LEGACY={URL:'https://example.com',TOKEN:'x'*43,CERT:'ab'*32}

def test_migrate_operator_credential_without_network_or_identity_change():
    async def case():
        store=MemoryStore();manager=ManagedConnection(store);session=Session()
        await manager.load(LEGACY);await manager.ensure_enrolled(session)
        assert manager.values==LEGACY and not session.calls
        second=ManagedConnection(store);await second.load();assert second.values==LEGACY
    asyncio.run(case())

def test_failed_private_save_does_not_mark_migration_done():
    async def case():
        manager=ManagedConnection(MemoryStore(fail=True));original=dict(LEGACY)
        with pytest.raises(OSError):await manager.load(LEGACY)
        assert manager.state is None and LEGACY==original
    asyncio.run(case())

def test_new_installation_uses_persisted_unique_identity_and_idempotent_enrollment():
    async def case():
        store=MemoryStore();m=ManagedConnection(store);await m.load()
        first=copy.deepcopy(store.value);assert first['enrolled'] is False
        other=ManagedConnection(MemoryStore());await other.load();assert other.values[TOKEN]!=m.values[TOKEN]
        again=ManagedConnection(store);await again.load();assert again.values==m.values
        session=Session();await again.ensure_enrolled(session);await again.ensure_enrolled(session)
        assert len(session.calls)==1 and store.value['enrolled'] is True
        url,kw=session.calls[0]
        assert url=='https://lottolab.toiss.kr/v1/ha/installations'
        assert kw['ssl'] is True and kw['allow_redirects'] is False
        assert set(kw['json'])=={'installation_id','credential'}
    asyncio.run(case())

def test_failure_preserves_identity_and_backs_off_without_token_form():
    async def case():
        store=MemoryStore();m=ManagedConnection(store);await m.load();old=copy.deepcopy(store.value);s=Session(503)
        for _ in range(2):
            with pytest.raises(LabServiceError):await m.ensure_enrolled(s)
        assert len(s.calls)==1 and store.value==old
    asyncio.run(case())

def test_corrupt_store_is_not_replaced_by_new_identity():
    async def case():
        store=MemoryStore({'version':9});m=ManagedConnection(store)
        with pytest.raises(ValueError):await m.load(LEGACY)
        assert store.value=={'version':9} and store.writes==0
    asyncio.run(case())

def test_clean_options_preserves_selection_profile_consent_and_removes_manual_controls():
    raw={**LEGACY,'generation_rules':{'fixed':[1]},'formula_options':{'x':1},'selected_methods':['uniform_floyd'],'saju_remote_consent':True}
    cleaned=without_user_connection(raw)
    assert cleaned=={'selected_methods':['uniform_floyd'],'saju_remote_consent':True}
    assert raw[TOKEN]==LEGACY[TOKEN]

def test_user_menus_have_no_transport_or_json_or_rule_steps():
    tree=ast.parse((R/'config_flow.py').read_text(encoding='utf-8'))
    names={n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
    assert not names & {'async_step_service','async_step_formula_options','async_step_generation_rules','async_step_reauth_confirm'}
    menus=[ast.literal_eval(k.value) for n in ast.walk(tree) if isinstance(n,ast.Call) for k in n.keywords if k.arg=='menu_options']
    assert menus==[['recommendations','saju','purchases']]
    for p in [R/'strings.json',*(R/'translations').glob('*.json')]:
        text=json.loads(p.read_text(encoding='utf-8'))
        assert not set(text.get('options',{}).get('step',{})) & {'service','formula_options','generation_rules'}

def test_old_request_journal_scope_is_unchanged():
    import hashlib
    tree=ast.parse((R/'service_runtime.py').read_text(encoding='utf-8'))
    method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_configure_connection')
    namespace={'hashlib':hashlib,'DOMAIN':'lotto_645','CONF_SERVICE_URL':URL,'CONF_SERVICE_TOKEN':TOKEN,'CONF_SERVICE_CERT':CERT,
        'LottoLabClient':lambda *a,**k:object(),'async_get_clientsession':lambda _:None,
        'Store':lambda h,v,key:key,'RemoteGeneration':lambda client,store:store}
    exec(compile(ast.Module(body=[method],type_ignores=[]),'<actual-runtime>','exec'),namespace)
    owner=SimpleNamespace(client=None,connection={},hass=None,entry=SimpleNamespace(entry_id='entry'))
    namespace['_configure_connection'](owner,LEGACY)
    old_scope=hashlib.sha256((LEGACY[URL]+'\0'+LEGACY[TOKEN]).encode()).hexdigest()[:24]
    assert owner.generator=='lotto_645.remote.entry.'+old_scope
    assert owner.ai_generator=='lotto_645.remote_ai.entry.'+old_scope

def test_removed_values_are_never_sent_to_generation():
    s=(R/'service_runtime.py').read_text(encoding='utf-8')
    assert "options.update(self.entry.options.get('formula_options'" not in s
    assert "options['generation_rules']" not in s
    assert 'async_start_reauth' not in s
