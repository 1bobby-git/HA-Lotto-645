"""Durable manual finalization state. Read/restart paths never send generation POSTs."""
from copy import deepcopy
import asyncio
import uuid
from .finalization_contract import parse_finalization, snapshot_hash
from .service_contract import identifier
from .lab_client import LabServiceError

TERMINAL=('completed','failed','cancelled')
REJECTED=('permission_denied','not_found','request_conflict','invalid_generation_request','usage_limited')

class RemoteFinalization:
    def __init__(self,client,store):
        self.client,self.store=client,store
        self._loaded=False;self._state={};self.lock=asyncio.Lock();self.load_lock=asyncio.Lock();self.ready=None

    async def load(self):
        async with self.load_lock:
            if self._loaded:return
            raw=await self.store.async_load()
            if raw is not None and (not isinstance(raw,dict) or raw.get('schema')!=1):raise ValueError('finalizer_storage_invalid')
            state=raw or {'schema':1,'selected_source':None,'pending':None,'last_result':None,'results':[]}
            for key in ('last_result','last_failure'):
                if state.get(key):state[key]=parse_finalization(state[key])
            if not isinstance(state.get('results',[]),list) or len(state.get('results',[]))>50:
                raise ValueError('finalizer_storage_invalid')
            state['results']=[parse_finalization(row) for row in state.get('results',[])]
            pending=state.get('pending')
            if pending:
                if not isinstance(pending,dict) or not isinstance(pending.get('body'),dict):raise ValueError('finalizer_storage_invalid')
                body=pending['body'];snapshot_hash(body.get('input_snapshot_hash'))
                for key in ('source_batch_id','source_selection_revision','request_key'):identifier(body.get(key))
                if type(body.get('game_count')) is not int or not 1<=body['game_count']<=20:raise ValueError('finalizer_storage_invalid')
                if pending.get('run_id'):identifier(pending['run_id'])
            self._state=state;self._loaded=True

    async def commit(self,state):
        if state==self._state:return
        await self.store.async_save(deepcopy(state))
        self._state=state

    async def state(self):
        await self.load();return deepcopy(self._state)

    async def select(self,batch,ids):
        async with self.lock:
            await self.load()
            if self._state.get('pending'):raise LabServiceError('finalization_pending')
            ready=await self.client.async_finalization_readiness(batch,ids)
            state=deepcopy(self._state);state['selected_source']={'source_batch_id':batch,'formula_ids':list(ids)}
            await self.commit(state);self.ready=ready
            return ready

    async def readiness(self,ids):
        await self.load();selected=self._state.get('selected_source')
        if not selected:return None
        self.ready=await self.client.async_finalization_readiness(selected['source_batch_id'],ids)
        return deepcopy(self.ready)

    async def start(self,count,ids,*,additional=False):
        async with self.lock:
            await self.load()
            if self._state.get('pending'):return await self._submit(self._state['pending']['body'])
            ready=await self.readiness(ids)
            if not ready or ready['input_state']!='ready':raise LabServiceError('sources_not_ready')
            sequence=0;previous=None
            if additional:
                last=next((row for row in reversed(self._state['results']) if row['input_snapshot_hash']==ready['input_snapshot_hash'] and row['requested_game_count']==count),None)
                if not last:raise LabServiceError('additional_run_requires_same_input')
                sequence=last['execution_sequence']+1;previous=last['finalization_run_id']
            body={key:ready[key] for key in ('source_batch_id','source_selection_revision','input_snapshot_hash')}
            body.update(game_count=count,formula_ids=list(ids),request_key=uuid.uuid4().hex,execution_sequence=sequence)
            if previous:body['previous_run_id']=previous
            state=deepcopy(self._state);state['pending']={'body':body,'run_id':None}
            await self.commit(state)
            return await self._submit(body)

    async def _submit(self,body):
        try:result=await self.client.async_start_finalization(body)
        except LabServiceError as error:
            if error.code in REJECTED:
                state=deepcopy(self._state);state['pending']=None
                await self.commit(state)
            raise
        return await self._accept(result)

    async def _accept(self,result):
        result=parse_finalization(result)
        state=deepcopy(self._state);pending=state.get('pending')
        if pending:
            body=pending['body']
            if any(result[key]!=body[other] for key,other in (('input_snapshot_hash','input_snapshot_hash'),('source_batch_id','source_batch_id'),('requested_game_count','game_count'))):
                raise LabServiceError('invalid_finalization_response')
            if pending.get('run_id') and pending['run_id']!=result['finalization_run_id']:
                raise LabServiceError('invalid_finalization_response')
        if result['job_status'] in TERMINAL:
            state['pending']=None
            state['last_result' if result['job_status']=='completed' else 'last_failure']=result
            rows=[row for row in state['results'] if row['finalization_run_id']!=result['finalization_run_id']]
            state['results']=(rows+[result])[-50:]
        elif pending:pending['run_id']=result['finalization_run_id']
        await self.commit(state)
        return deepcopy(result)

    async def poll(self):
        async with self.lock:
            await self.load();pending=self._state.get('pending')
            if not pending:
                last=self._state.get('last_result')
                if not last:return None
                result=await self.client.async_get_finalization(last['finalization_run_id'])
                if result==last:return deepcopy(last)
                return await self._accept(result)
            try:
                result=await self.client.async_get_finalization(pending['run_id']) if pending.get('run_id') else await self.client.async_finalization_by_key(pending['body']['request_key'])
            except LabServiceError as error:
                if error.code=='not_found':return None
                raise
            return await self._accept(result)

    async def cancel(self):
        async with self.lock:
            await self.load();pending=self._state.get('pending')
            if not pending:return None
            if not pending.get('run_id'):
                response=await self.client.async_cancel_finalization_request(pending['body']['request_key'])
                if response.get('finalization_run_id'):return await self._accept(response)
                state=deepcopy(self._state);state['pending']=None
                await self.commit(state);return None
            return await self._accept(await self.client.async_cancel_finalization(pending['run_id']))

    def purchase_matches(self,target,values):
        """Freeze evidence only when the user explicitly saves matching ticket numbers."""
        from .purchased_tickets import parse_games
        found={}
        for bought in parse_games(values):
            for bundle in reversed(self._state.get('results',[])):
                if bundle.get('job_status')!='completed' or bundle.get('target_round')!=target or bundle.get('evaluation_mode')!='live':continue
                game=next((row for row in bundle['games'] if row['numbers']==bought['numbers']),None)
                if game:
                    found[bought['slot']]={'finalizer_id':bundle['finalizer_id'],'bundle_generation_id':bundle['bundle_generation_id'],
                        'game_id':game['game_id'],'input_snapshot_hash':bundle['input_snapshot_hash'],'numbers':list(game['numbers'])}
                    break
        return found
