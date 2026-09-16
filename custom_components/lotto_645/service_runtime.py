"""HA orchestration for the private Core service. No lottery calculation code."""
from __future__ import annotations
import asyncio
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
import hmac
import json
import time
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from .const import DOMAIN, CONF_SERVICE_URL, CONF_SERVICE_TOKEN, CONF_SERVICE_CERT, CONF_PERSONAL_CONSENT
from .lab_client import LottoLabClient, LabServiceError
from .remote_generation import RemoteGeneration
from .managed_connection import ManagedConnection, CONNECTION_KEYS, without_user_connection
from .service_contract import Catalog, numbers
from .methods import install_catalog, METHOD_MYUNGRI_HETU, METHODS_BY_ID
from .models import AnalysisResult, Recommendation

class ServiceRuntime:
    def __init__(self, owner):
        self.owner = owner
        self.hass = owner.hass
        self.entry = owner.entry
        self.client = None
        self.catalog = None
        self.catalog_updated_at = 0.0
        self.status = 'not_connected'
        self.info = {}
        self.retry_task = None
        self.lock = asyncio.Lock()
        self._failed_context = None
        self.connection = {}
        self.connection_manager = ManagedConnection(Store(self.hass, 1, f'{DOMAIN}.connection.{self.entry.entry_id}'))
        self.catalog_store = Store(self.hass,1,f'{DOMAIN}.catalog.{self.entry.entry_id}')
        self.generator = None
        self.ai_generator = None

    def _configure_connection(self, values):
        if self.client is not None and self.connection == values:
            return
        self.connection = dict(values)
        self.client = LottoLabClient(async_get_clientsession(self.hass),
            values[CONF_SERVICE_URL], values[CONF_SERVICE_TOKEN],
            certificate_sha256=values.get(CONF_SERVICE_CERT))
        scope=self.connection_manager.journal_scope
        self.generator=RemoteGeneration(self.client,Store(self.hass,1,f'{DOMAIN}.remote.{self.entry.entry_id}.{scope}'))
        self.ai_generator=RemoteGeneration(self.client,Store(self.hass,1,f'{DOMAIN}.remote_ai.{self.entry.entry_id}.{scope}'))

    async def prepare(self):
        if self.catalog is None:
            try:
                saved = await self.catalog_store.async_load()
                if saved:
                    self.catalog = Catalog.parse(saved)
                    install_catalog(self.catalog)
            except (ValueError, OSError):
                pass
        try:
            legacy = {**dict(self.entry.data), **dict(self.entry.options)}
            await self.connection_manager.load(legacy)
            data = without_user_connection(self.entry.data)
            options = without_user_connection(self.entry.options)
            if data != dict(self.entry.data) or options != dict(self.entry.options):
                self.hass.config_entries.async_update_entry(self.entry, data=data, options=options)
            await self.connection_manager.ensure_enrolled(async_get_clientsession(self.hass))
            self._configure_connection(self.connection_manager.values)
        except (OSError, ValueError, LabServiceError) as exc:
            self.status = exc.code if isinstance(exc,LabServiceError) else 'managed_storage_error'
            return
        try:
            catalog = await self.client.async_catalog()
            info = await self.client.async_service_info()
            # Build a fresh public catalog; never save the transport token here.
            raw = {'contract_version':1,'core_version':catalog.core_version,
                   'default_method_ids':list(catalog.default_method_ids),
                   'methods':[asdict(row) for row in catalog.methods]}
            await self.catalog_store.async_save(raw)
            self.catalog = catalog
            self.info = info
            install_catalog(catalog)
            self.status = 'ready'
            self.catalog_updated_at = time.monotonic()
        except (LabServiceError, OSError, ValueError) as exc:
            self.status = exc.code if isinstance(exc,LabServiceError) else 'catalog_storage_error'
            if self.status == 'reauth_required':
                self.connection_manager.invalidate()

    def legacy_analysis(self):
        target = self.owner.history[-1].round+1
        snapshot = self.owner._prediction_snapshot or {}
        rows=[]
        if snapshot.get('target_round') == target:
            for raw in snapshot.get('recommendations',[]):
                if raw.get('method_id') in self.owner.selected_method_ids:
                    try:
                        item=Recommendation.from_storage(raw)
                        rows.append(Recommendation(item.index,item.method_id,item.label,item.method,
                            item.numbers,'기존 기기에 저장된 번호입니다. 새 Core에서 생성한 기록이 아닙니다.',
                            None,item.details,source='legacy_local'))
                    except (ValueError,KeyError,TypeError):
                        continue
        return AnalysisResult(target,target-1,tuple(rows),{
            'selected_method_ids':list(self.owner.selected_method_ids),
            'generation_sequence':self.owner._local_generation_nonce,
            'service_status':self.status,'record_origin':'legacy_local'})

    def material_context(self, options, profile):
        # Local digest is keyed so it does not become a public birth-date oracle.
        content=json.dumps({'options':options,'profile':profile,'origin':self.connection.get(CONF_SERVICE_URL),
                            'device':self.info.get('device_id')},sort_keys=True,ensure_ascii=False).encode()
        return hmac.new(self.connection_manager.context_secret.encode(),content,hashlib.sha256).hexdigest()

    @staticmethod
    def analysis_from_saved(saved, ids, nonce, status):
        rows=[]
        for row in saved.get('games',[]):
            if row.get('status')!='generated' or row['formula_id'] not in ids:
                continue
            values=numbers(row['numbers'])
            rows.append(Recommendation(len(rows)+1,row['formula_id'],row['name'],row['category'],
                values,row['public_reason'],None,{
                    'formula_id':row['formula_id'],'formula_version':row['formula_version'],
                    'core_version':saved['core_version'],'generation_id':saved['generation_id'],
                    'generated_at':saved['generated_at'],'consensus_updated_at':saved['generated_at'],
                    'target_round':saved['target_round'],'based_on_round':saved['based_on_round'],
                    'method_description':row['public_reason'],
                },source='core_service'))
        return AnalysisResult(saved['target_round'],saved['based_on_round'],tuple(rows),{
            'selected_method_ids':list(ids),'generation_sequence':nonce,
            'core_version':saved['core_version'],'generation_id':saved['generation_id'],
            'service_status':status,'record_origin':'server',
            'unavailable_methods':[r['formula_id'] for r in saved.get('games',[]) if r['status']=='unavailable']})

    async def _finish_or_schedule(self, manager, result):
        # Small interactive wait; long calculations are polled without blocking HA setup.
        for _ in range(8):
            if result.status in ('completed','failed','cancelled'):
                return result
            await asyncio.sleep(.4)
            result=await manager.poll()
        if self.retry_task is None or self.retry_task.done():
            self.retry_task=self.hass.async_create_task(self._follow(manager), 'lotto-service-follow')
        return result

    async def _follow(self, manager):
        try:
            for _ in range(100):
                await asyncio.sleep(2)
                result=await manager.poll()
                if result is None or result.status in ('completed','failed','cancelled'):
                    await self.owner.async_request_refresh()
                    return
        except (LabServiceError,OSError,ValueError):
            self.status='connection_unavailable'
            self.owner.async_update_listeners()

    async def analysis(self):
        async with self.lock:
            return await self._analysis()

    async def _analysis(self):
        if self.connection_manager.needs_refresh:
            await self.prepare()
        if not self.client:
            await self.prepare()
        if not self.client:
            return self.legacy_analysis()
        if self.catalog is None or time.monotonic()-self.catalog_updated_at>3600 or self.status in ('connection_unavailable','reauth_required'):
            await self.prepare()
        ids=self.owner.selected_method_ids
        target=self.owner.history[-1].round+1
        options={}
        # Deprecated manual generation rules and JSON overrides are not applied.
        profile=self.owner.saju_profile if METHOD_MYUNGRI_HETU in ids else None
        material=self.material_context(options,profile)
        context_tag=hashlib.sha256(json.dumps([target,ids,material,self.owner._local_generation_nonce]).encode()).hexdigest()
        manager=self.generator
        state=await manager.state()
        if state.get('pending'):
            try:
                result=await manager.poll()
                result=await self._finish_or_schedule(manager,result)
            except LabServiceError as exc:
                pending=state['pending']
                if exc.code=='not_found' and not pending.get('generation_id') and pending.get('context_tag')==context_tag:
                    result=await manager.start(target_round=target,formula_ids=ids,options=options,
                        personal_profile=profile,personal_consent=bool(self.entry.options.get(CONF_PERSONAL_CONSENT)),
                        context_tag=context_tag,mode=pending.get('mode','generate'),
                        source_generation_id=pending.get('source_generation_id'),
                        material_context=material,nonce=self.owner._local_generation_nonce)
                    result=await self._finish_or_schedule(manager,result)
                else:
                    self.status='pending_recovery_required'
                    return self._previous_analysis(state)
            state=await manager.state()
            if state.get('pending'):
                self.status='generating'
                return self._previous_analysis(state)
        previous=state.get('last_result')
        previous_context=state.get('last_context',{})
        if previous and previous_context.get('context_tag')==context_tag:
            self.status='ready'
            self.owner._local_generated_at=datetime.fromisoformat(previous['generated_at'])
            return self.analysis_from_saved(previous,ids,self.owner._local_generation_nonce,self.status)
        if not ids:
            self.status='profile_or_selection_required'
            return self._previous_analysis(state)
        if self._failed_context==context_tag or (state.get('last_failure') or {}).get('context_tag')==context_tag:
            self.status=(state.get('last_failure') or {}).get('status','failed')
            return self._previous_analysis(state)
        if any(METHODS_BY_ID[x].status=='withdrawn' for x in ids):
            self.status='formula_withdrawn'
            return self._previous_analysis(state)
        source=previous['generation_id'] if previous and previous['target_round']==target else None
        mode='generate'
        # Reconcile only when the formula set changes but the underlying inputs do not.
        if (source and self.catalog is not None and previous['core_version']==self.catalog.core_version
            and previous_context.get('material_context')==material
            and previous_context.get('nonce')==self.owner._local_generation_nonce):
            mode='reconcile'
        try:
            result=await manager.start(target_round=target, formula_ids=ids,options=options,
                personal_profile=profile,personal_consent=bool(self.entry.options.get(CONF_PERSONAL_CONSENT)),
                context_tag=context_tag,mode=mode,source_generation_id=source,
                material_context=material,nonce=self.owner._local_generation_nonce)
            result=await self._finish_or_schedule(manager,result)
            state=await manager.state()
            if result.status=='completed':
                self.status='ready'
                self.owner._local_generated_at=datetime.fromisoformat(result.generated_at)
                self.owner._needs_storage_save=True
                return self.analysis_from_saved(asdict(result),ids,self.owner._local_generation_nonce,self.status)
            self.status='generating' if result.status in ('queued','running') else result.status
            if result.status in ('failed','cancelled'):
                self._failed_context=context_tag
        except (LabServiceError,OSError,ValueError) as exc:
            self.status=exc.code if isinstance(exc,LabServiceError) else 'service_storage_error'
            if self.status=='reauth_required':
                self.connection_manager.invalidate()
        return self._previous_analysis(state)

    def _previous_analysis(self,state):
        old=state.get('last_result')
        target=self.owner.history[-1].round+1
        if old and old['target_round']==target:
            return self.analysis_from_saved(old,self.owner.selected_method_ids,
                self.owner._local_generation_nonce,self.status)
        return self.legacy_analysis()

    async def ai_ticket(self,target):
        if self.connection_manager.needs_refresh:
            await self.prepare()
        if not self.client:
            raise LabServiceError('not_connected')
        from .ai_formula import AI_BASE_FORMULA
        normal=await self.generator.saved_result()
        source=normal['generation_id'] if normal and normal['target_round']==target else None
        result=await self.ai_generator.start(target_round=target,formula_ids=[AI_BASE_FORMULA],
            mode='ai_base',source_generation_id=source)
        for _ in range(90):
            if result.status not in ('queued','running'):
                break
            await asyncio.sleep(2)
            result=await self.ai_generator.poll()
        if result.status!='completed' or not result.games or result.games[0].status!='generated':
            raise LabServiceError('ai_base_unavailable')
        return result

    async def close(self):
        if self.retry_task and not self.retry_task.done():
            self.retry_task.cancel()
            await asyncio.gather(self.retry_task,return_exceptions=True)
