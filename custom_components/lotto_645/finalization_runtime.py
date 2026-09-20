"""Optional post-generation orchestration, independent from source generation state."""
import asyncio
from .const import DOMAIN
from .lab_client import LabServiceError
from .remote_finalization import RemoteFinalization
from .finalization_contract import CAPABILITY

class FinalizationRuntime:
    def finalization_ids(self):
        return list(getattr(self.owner,'configured_method_ids',self.owner.selected_method_ids))

    async def finalization_state(self,action='refresh',data=None):
        try:return await self._finalization_state(action,data)
        except (LabServiceError,OSError,ValueError):
            self.final_summary.update(connection_status='unavailable',default_execution_ready=False)
            self.owner.async_update_listeners()
            raise

    async def _finalization_state(self,action='refresh',data=None):
        data=data or {}
        if not self.client or self.connection_manager.needs_refresh:await self.prepare()
        if not self.client or CAPABILITY not in self.info.get('capabilities',[]):
            raise LabServiceError('finalization_not_supported')
        await self._resume_finalizer()
        finalizer=self.finalizer;state=await finalizer.state();original=await self.generator.state()
        ids=self.finalization_ids()
        latest=(original['pending'].get('generation_id') if original.get('pending') else (original.get('last_result') or {}).get('generation_id'))
        if action=='cancel':await finalizer.cancel()
        elif action not in ('refresh','select','start'):raise LabServiceError('invalid_finalization_action')
        if action=='select':
            batch=data.get('source_batch_id') or latest
            if not batch:raise LabServiceError('sources_not_ready')
            await finalizer.select(batch,ids)
        elif not state.get('selected_source') and latest:
            try:await finalizer.select(latest,ids)
            except LabServiceError:pass
        state=await finalizer.state()
        try:ready=await finalizer.readiness(ids)
        except LabServiceError as error:
            ready={'input_state':'blocked','expected_count':len(ids),'completed_count':0,
                   'source_batch_id':(state.get('selected_source') or {}).get('source_batch_id'),
                   'blocked_sources':[{'formula_id':None,'reason':error.code}]}
        if action=='start':
            if not ready or ready['input_state']!='ready':raise LabServiceError('sources_not_ready')
            if any(data.get(k) is not None and data[k]!=ready.get(k) for k in ('source_batch_id','source_selection_revision','input_snapshot_hash')):
                raise LabServiceError('request_conflict')
            count=data.get('game_count',ready.get('default_game_count'))
            if type(count) is not int or not ready['min_game_count']<=count<=ready['max_game_count']:
                raise LabServiceError('choose_feasible_game_count')
            await finalizer.start(count,ids,additional=data.get('additional') is True)
            await self._resume_finalizer()
        await finalizer.poll();state=await finalizer.state()
        ready=ready or {'input_state':'not_configured','expected_count':len(ids),'completed_count':0}
        terminal=state.get('results',[])
        last=terminal[-1] if terminal else {}
        self.final_summary={'input_state':ready['input_state'],'completed_count':ready['completed_count'],
            'expected_count':ready['expected_count'],'job_status':'running' if state.get('pending') else last.get('job_status','not_started'),
            'default_execution_ready':ready['input_state']=='ready' and all(type(ready.get(k)) is int for k in ('min_game_count','default_game_count','max_game_count')) and ready['min_game_count']<=ready['default_game_count']<=ready['max_game_count'],'game_count':last.get('actual_game_count',0),'completed_at':last.get('result_committed_at')}
        self.owner.async_update_listeners()
        return {'readiness':ready,'state':state,'latest_source_batch_id':latest,
                'local_ai_supported':False,'summary':self.final_summary}

    async def _resume_finalizer(self):
        from homeassistant.helpers.storage import Store
        if CAPABILITY not in self.info.get('capabilities',[]):return
        if self.finalizer is None:
            scope=self.connection_manager.journal_scope
            store=Store(self.hass,1,f'{DOMAIN}.finalization.{self.entry.entry_id}.{scope}')
            self.finalizer=RemoteFinalization(self.client,store)
        state=await self.finalizer.state()
        if state.get('pending') and (not self.final_follow or self.final_follow.done()):
            self.final_follow=self.hass.async_create_task(self._follow_finalizer(),'lotto-finalization-follow')

    async def _follow_finalizer(self):
        manager=self.finalizer
        try:
            for _ in range(120):
                if manager is not self.finalizer:return
                result=await manager.poll()
                if manager is not self.finalizer:return
                if result:
                    self.final_summary.update(job_status=result['job_status'],game_count=result['actual_game_count'],completed_at=result['result_committed_at'])
                    self.owner.async_update_listeners()
                    self.hass.bus.async_fire(DOMAIN+'_updated',{'entry_id':self.entry.entry_id})
                    if result['job_status'] in ('completed','failed','cancelled'):return
                await asyncio.sleep(2)
        except (LabServiceError,OSError,ValueError):
            if manager is self.finalizer:
                self.final_summary['connection_status']='unavailable'
                self.owner.async_update_listeners()
