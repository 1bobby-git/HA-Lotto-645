"""Focused tests for managed connection, preserved journals and removed UI."""
import asyncio
import ast
import copy
import hashlib
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

def test_unapproved_installation_never_enrolls_anonymously():
    async def case():
        store=MemoryStore();m=ManagedConnection(store);await m.load()
        original=copy.deepcopy(store.value);session=Session()
        with pytest.raises(LabServiceError,match='member_link_required'):
            await m.ensure_enrolled(session)
        assert not session.calls and store.value==original
    asyncio.run(case())


def test_member_refresh_preserves_identity_and_recovers_lost_response(monkeypatch):
    from custom_components.lotto_645.member_link import state_from_tokens
    import custom_components.lotto_645.member_link as link
    async def case():
        old={'version':1,'source':'operator','credentials':LEGACY,'enrolled':True}
        tokens={'access_token':'a'*43,'refresh_token':'b'*64,'device_id':'c'*32,'expires_in':900}
        saved=state_from_tokens(tokens,old);saved['access_expires_at']=0
        store=MemoryStore(saved);m=ManagedConnection(store);await m.load();scope=m.journal_scope;secret=m.context_secret;calls=[]
        async def exchange(session,path,body):
            calls.append(dict(body))
            if len(calls)==1:raise LabServiceError('member_service_unavailable')
            return {**tokens,'token_type':'Bearer','access_token':'d'*43,'refresh_token':'e'*64}
        monkeypatch.setattr(link,'request',exchange)
        with pytest.raises(LabServiceError):await m.ensure_enrolled(None)
        restarted=ManagedConnection(store);await restarted.load();await restarted.ensure_enrolled(None)
        assert calls[0]['rotation_id']==calls[1]['rotation_id']
        assert restarted.journal_scope==scope and restarted.context_secret==secret
        assert restarted.values[TOKEN]=='d'*43 and 'pending_rotation' not in store.value
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
    assert menus==[['account','recommendations','saju','purchases']]
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
    owner=SimpleNamespace(client=None,connection={},hass=None,entry=SimpleNamespace(entry_id='entry'),connection_manager=SimpleNamespace(journal_scope=hashlib.sha256((LEGACY[URL]+'\0'+LEGACY[TOKEN]).encode()).hexdigest()[:24]))
    namespace['_configure_connection'](owner,LEGACY)
    old_scope=hashlib.sha256((LEGACY[URL]+'\0'+LEGACY[TOKEN]).encode()).hexdigest()[:24]
    assert owner.generator=='lotto_645.remote.entry.'+old_scope
    assert owner.ai_generator=='lotto_645.remote_ai.entry.'+old_scope

OLD_ORIGIN='https://lottolab.toiss.kr'
NEW_ORIGIN='https://lotto.formulab.kr'

def test_service_origin_points_to_current_domain():
    from custom_components.lotto_645.managed_connection import DEFAULT_SERVICE_URL
    from custom_components.lotto_645 import member_link
    assert DEFAULT_SERVICE_URL==NEW_ORIGIN
    assert member_link.ORIGIN==NEW_ORIGIN

def test_retired_origin_is_rewritten_without_identity_change():
    async def case():
        old={'version':1,'source':'member','credentials':{URL:OLD_ORIGIN,TOKEN:'t'*43,CERT:''},
             'enrolled':True,'device_id':'d'*32,'refresh_token':'r'*64,'access_expires_at':0}
        old_scope=hashlib.sha256((OLD_ORIGIN+'\0'+'t'*43).encode()).hexdigest()[:24]
        store=MemoryStore(old);manager=ManagedConnection(store);await manager.load()
        assert manager.values[URL]==NEW_ORIGIN
        assert manager.values[TOKEN]=='t'*43
        assert store.value['credentials'][URL]==NEW_ORIGIN
        assert manager.journal_scope==old_scope
        assert store.value['journal_scope']==old_scope
        assert store.value['refresh_token']=='r'*64 and store.value['device_id']=='d'*32
    asyncio.run(case())

def test_retired_origin_migration_failure_keeps_previous_state():
    async def case():
        old={'version':1,'source':'member','credentials':{URL:OLD_ORIGIN,TOKEN:'t'*43,CERT:''},'enrolled':True}
        store=MemoryStore(old,fail=True);manager=ManagedConnection(store)
        with pytest.raises(OSError):await manager.load()
        assert manager.state is None and store.value==old
    asyncio.run(case())

def test_unrelated_origin_is_never_rewritten():
    async def case():
        saved={'version':1,'source':'operator','credentials':dict(LEGACY),'enrolled':True}
        store=MemoryStore(saved);manager=ManagedConnection(store);await manager.load()
        assert manager.values==LEGACY and store.value==saved and store.writes==0
    asyncio.run(case())

def test_removed_values_are_never_sent_to_generation():
    s=(R/'service_runtime.py').read_text(encoding='utf-8')
    assert "options.update(self.entry.options.get('formula_options'" not in s
    assert "options['generation_rules']" not in s
    assert 'async_start_reauth' not in s


def test_simultaneous_member_refresh_shares_one_persisted_rotation(monkeypatch):
    from custom_components.lotto_645.member_link import state_from_tokens
    import custom_components.lotto_645.member_link as link
    async def case():
        tokens={'access_token':'a'*43,'refresh_token':'b'*64,'device_id':'c'*32,'expires_in':900}
        saved=state_from_tokens(tokens);saved['access_expires_at']=0
        store=MemoryStore(saved);manager=ManagedConnection(store);await manager.load()
        scope=manager.journal_scope;calls=[]
        async def exchange(session,path,body):
            calls.append(dict(body));await asyncio.sleep(.03)
            return {**tokens,'token_type':'Bearer','access_token':'d'*43,'refresh_token':'e'*64}
        monkeypatch.setattr(link,'request',exchange)
        await asyncio.gather(manager.ensure_enrolled(None),manager.ensure_enrolled(None))
        assert len(calls)==1
        assert manager.values[TOKEN]=='d'*43 and manager.journal_scope==scope
        assert 'pending_rotation' not in store.value
    asyncio.run(case())


def test_refresh_token_updates_inflight_client_without_replacing_journals():
    tree=ast.parse((R/'service_runtime.py').read_text(encoding='utf-8'))
    method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_configure_connection')
    class Client:
        def __init__(self,session,url,token,**kwargs):self.token=token
        def set_access_token(self,value):self.token=value
    namespace={'DOMAIN':'lotto_645','CONF_SERVICE_URL':URL,'CONF_SERVICE_TOKEN':TOKEN,'CONF_SERVICE_CERT':CERT,
        'LottoLabClient':Client,'async_get_clientsession':lambda _:None,
        'Store':lambda h,v,key:key,'RemoteGeneration':lambda client,store:SimpleNamespace(client=client,store=store)}
    exec(compile(ast.Module(body=[method],type_ignores=[]),'<actual-runtime>','exec'),namespace)
    owner=SimpleNamespace(client=None,connection={},hass=None,entry=SimpleNamespace(entry_id='entry'),
        connection_manager=SimpleNamespace(journal_scope='fixed-device-journal'))
    apply=namespace['_configure_connection'];apply(owner,LEGACY)
    before=owner.client;pending=owner.generator;ai=owner.ai_generator
    apply(owner,{**LEGACY,TOKEN:'rotated-access-token-1234567890'})
    assert owner.client is before and owner.generator is pending and owner.ai_generator is ai
    assert pending.client.token=='rotated-access-token-1234567890'
    assert owner.connection[TOKEN]==pending.client.token
