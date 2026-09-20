import asyncio,json,secrets
from copy import deepcopy
from types import SimpleNamespace
import pytest
from test_finalization_client import Client,Store,ready,result
from custom_components.lotto_645.remote_finalization import RemoteFinalization
from custom_components.lotto_645.finalization_contract import parse_finalization
from custom_components.lotto_645.lab_client import LottoLabClient,LabServiceError
from custom_components.lotto_645.finalization_runtime import FinalizationRuntime

@pytest.mark.parametrize('method',['async_get_finalization','async_cancel_finalization'])
def test_transport_rejects_other_run_id(method):
 async def run():
  client=LottoLabClient(None,'https://example.invalid',secrets.token_urlsafe(24))
  async def wrong(*args,**kwargs):return result()
  client._request=wrong
  with pytest.raises(LabServiceError,match='invalid_finalization_response'):
   await getattr(client,method)('another-run')
 asyncio.run(run())

def test_private_fields_are_not_saved_in_public_dtos():
 raw=result();raw['private_payload']={'value':'never-save-this'}
 raw['games'][0]['private_payload']='never-save-this'
 raw['source_games'][0]['private_payload']='never-save-this'
 raw['metrics']={'audit':{'final':{'coverage_3':.1,'private_payload':'never-save-this'}},'search':{},'comparison':{}}
 cleaned=parse_finalization(raw)
 assert 'never-save-this' not in json.dumps(cleaned)
 assert cleaned['metrics']['audit']['final']['coverage_3']==.1

def test_rejected_manual_post_can_be_corrected_without_stuck_pending():
 async def run():
  client=Client();store=Store();manager=RemoteFinalization(client,store)
  await manager.select('source-1',['formula-a','formula-b'])
  async def reject(body):raise LabServiceError('usage_limited')
  client.async_start_finalization=reject
  with pytest.raises(LabServiceError):await manager.start(2,['formula-a','formula-b'])
  assert store.data['pending'] is None
 asyncio.run(run())

def test_zero_completed_inputs_never_enable_native_execution():
 async def run():
  owner=SimpleNamespace(selected_method_ids=['a','b'],configured_method_ids=['a','b'],async_update_listeners=lambda:None)
  runtime=FinalizationRuntime();runtime.owner=owner;runtime.client=object();runtime.final_summary={}
  runtime.connection_manager=SimpleNamespace(needs_refresh=False);runtime.info={'capabilities':['post_generation_ticket_set_v1']}
  async def state():return {'pending':None,'selected_source':{'source_batch_id':'source'},'results':[]}
  async def missing(ids):return {'input_state':'blocked','expected_count':2,'completed_count':0,'min_game_count':None,'max_game_count':0,'default_game_count':2}
  async def nothing():return None
  runtime.finalizer=SimpleNamespace(state=state,readiness=missing,poll=nothing)
  runtime.generator=SimpleNamespace(state=state);runtime._resume_finalizer=nothing
  response=await runtime.finalization_state()
  assert response['summary']['default_execution_ready'] is False
 asyncio.run(run())
