"""Manual second-stage state never overwrites original generation or purchases."""
import asyncio
from copy import deepcopy
import pytest
from test_analysis_engine import ROOT
from custom_components.lotto_645.finalization_contract import parse_finalization,parse_readiness,CAPABILITY,FINALIZER_ID
from custom_components.lotto_645.remote_finalization import RemoteFinalization
from custom_components.lotto_645.service_contract import ContractError
from custom_components.lotto_645.lab_client import LabServiceError


def ready():
    return {'capability':CAPABILITY,'input_state':'ready','source_batch_id':'source-1','source_selection_revision':'rev-1','input_snapshot_hash':'a'*64,
        'expected_count':2,'completed_count':2,'source_formula_ids':['formula-a','formula-b'],'blocked_sources':[],
        'target_round':1243,'based_on_round':1242,'min_game_count':2,'max_game_count':20,'default_game_count':2}


def result(state='completed'):
    return {'contract_version':1,'capability':CAPABILITY,'execution_stage':'post_generation','trigger':'manual','output_kind':'ticket_set',
        'finalizer_id':FINALIZER_ID,'job_status':state,'finalization_run_id':'final-1','bundle_generation_id':'final-1','source_batch_id':'source-1',
        'input_snapshot_hash':'a'*64,'target_round':1243,'based_on_round':1242,'requested_game_count':2,'actual_game_count':2 if state=='completed' else 0,
        'games':[{'game_id':'g01','numbers':[1,2,3,4,5,6]},{'game_id':'g02','numbers':[7,8,9,10,11,12]}] if state=='completed' else [],
        'candidate_numbers':list(range(1,13)),'source_games':[{'formula_id':'formula-a','numbers':[1,2,3,4,5,6]},{'formula_id':'formula-b','numbers':[7,8,9,10,11,12]}],
        'execution_sequence':0,'result_committed_at':'2026-09-20T00:00:00+00:00','evaluation_mode':'live'}

class Store:
    def __init__(self):self.data=None;self.fail=False
    async def async_load(self):return deepcopy(self.data)
    async def async_save(self,value):
        if self.fail:raise OSError('synthetic write failure')
        self.data=deepcopy(value)

class Client:
    def __init__(self):self.posts=0;self.keys=[];self.exists=False;self.fail=False
    async def async_finalization_readiness(self,batch,ids):return ready()
    async def async_start_finalization(self,body):
        self.posts+=1;self.keys.append(body['request_key']);self.exists=True
        if self.fail:raise LabServiceError('timeout')
        return parse_finalization(result('running'))
    async def async_finalization_by_key(self,key):
        if not self.exists:raise LabServiceError('not_found')
        return parse_finalization(result())
    async def async_get_finalization(self,run):return parse_finalization(result())
    async def async_cancel_finalization(self,run):return parse_finalization(result('cancelled'))
    async def async_cancel_finalization_request(self,key):return {'cancelled_request':True,'request_key':key,'job_created':False}

@pytest.mark.parametrize('change',[{'completed_count':1},{'expected_count':18},{'source_formula_ids':['formula-a','formula-a']},{'based_on_round':1241},{'blocked_sources':[{'reason':'unavailable'}]}])
def test_readiness_does_not_trust_ready_string(change):
    with pytest.raises(ContractError):parse_readiness({**ready(),**change})

@pytest.mark.parametrize('change',[{'actual_game_count':1},{'games':[]},{'candidate_numbers':[1,2,3,4,5,6]},{'trigger':'automatic'},
    {'output_kind':'single_game'},{'execution_stage':'generation'},{'bundle_generation_id':'other'},{'source_games':[]},{'based_on_round':1241}])
def test_ticket_set_cannot_replace_original_single_game_contract(change):
    with pytest.raises(ContractError):parse_finalization({**result(),**change})


def test_manual_persistence_restart_and_read_only_poll():
    async def run():
        store=Store();client=Client();manager=RemoteFinalization(client,store)
        await manager.select('source-1',['formula-a','formula-b'])
        for _ in range(5):await manager.readiness(['formula-a','formula-b']);await manager.poll()
        assert client.posts==0
        client.fail=True
        with pytest.raises(LabServiceError):await manager.start(2,['formula-a','formula-b'])
        assert store.data['pending']['body']['request_key']==client.keys[0]
        restarted=RemoteFinalization(client,store);await restarted.poll()
        assert client.posts==1 and (await restarted.state())['pending'] is None
        before=deepcopy(store.data['last_result']);await restarted.select('source-2',['formula-a','formula-b'])
        assert store.data['last_result']==before
        assert not any(key in store.data for key in ('nonce','last_generated','original_pending'))
    asyncio.run(run())


def test_missing_reply_after_restart_never_reissues_a_post():
    async def run():
        store=Store();client=Client();manager=RemoteFinalization(client,store)
        await manager.select('source-1',['formula-a','formula-b']);client.fail=True
        with pytest.raises(LabServiceError):await manager.start(2,['formula-a','formula-b'])
        client.exists=False;restarted=RemoteFinalization(client,store)
        for _ in range(3):assert await restarted.poll() is None
        assert client.posts==1 and store.data['pending'] is not None
        await restarted.cancel();assert store.data['pending'] is None and client.posts==1
    asyncio.run(run())


def test_disk_failure_prevents_manual_submission():
    async def run():
        store=Store();client=Client();manager=RemoteFinalization(client,store)
        await manager.select('source-1',['formula-a','formula-b']);store.fail=True
        with pytest.raises(OSError):await manager.start(2,['formula-a','formula-b'])
        assert client.posts==0 and store.data['pending'] is None
    asyncio.run(run())


def test_corrupt_final_store_is_not_overwritten():
    async def run():
        store=Store();store.data={'schema':99};manager=RemoteFinalization(Client(),store)
        with pytest.raises(ValueError):await manager.load()
        assert store.data=={'schema':99}
    asyncio.run(run())
