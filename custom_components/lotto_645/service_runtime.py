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
from .const import DOMAIN, CONF_SERVICE_URL, CONF_SERVICE_TOKEN, CONF_SERVICE_CERT, CONF_PERSONAL_CONSENT, MAX_GAMES_PER_FORMULA
from .lab_client import LottoLabClient, LabServiceError
from .remote_generation import RemoteGeneration, retry_due
from .managed_connection import ManagedConnection, CONNECTION_KEYS, without_user_connection
from .member_link import poll as poll_member_link, state_from_tokens
from .service_contract import Catalog, numbers
from .game_batches import merge_batches, next_batch, shortfalls
from .methods import install_catalog, METHOD_MYUNGRI_HETU, METHODS_BY_ID
from .models import AnalysisResult, Recommendation

from .finalization_runtime import FinalizationRuntime

class ServiceRuntime(FinalizationRuntime):
    def __init__(self, owner):
        self.owner = owner
        self.hass = owner.hass
        self.entry = owner.entry
        self.client = None
        self.catalog = None
        self.catalog_updated_at = 0.0
        self.status = 'not_connected'
        self.info = {}
        self.retry_tasks = set()
        self.lock = asyncio.Lock()
        self.connection = {}
        self.connection_manager = ManagedConnection(Store(self.hass, 1, f'{DOMAIN}.connection.{self.entry.entry_id}'))
        self.catalog_store = Store(self.hass,1,f'{DOMAIN}.catalog.{self.entry.entry_id}')
        self.generator = None
        self.generators = {}
        self.ai_generator = None
        self.finalizer = None
        self.final_follow = None
        self.final_summary = {}
        self.health = {}
        self.member_link = None
        self.member_task = None

    def _remote_manager(self, index):
        """Return the durable remote job slot of one generation batch.

        Batch 0 keeps the original store key so an existing single-game result
        or pending job is reused instead of regenerated. Later batches get their
        own key, which keeps every accepted result durable across restarts.
        """
        manager=self.generators.get(index)
        if manager is not None:
            return manager
        scope=self.connection_manager.journal_scope
        key=f'{DOMAIN}.remote.{self.entry.entry_id}.{scope}'
        if index:
            key=f'{key}.g{index+1}'
        manager=RemoteGeneration(self.client,Store(self.hass,1,key))
        self.generators[index]=manager
        return manager

    def _configure_connection(self, values):
        scope = self.connection_manager.journal_scope
        same_endpoint = all(self.connection.get(k) == values.get(k)
                            for k in (CONF_SERVICE_URL, CONF_SERVICE_CERT))
        if (self.client is not None and same_endpoint
                and getattr(self, '_configured_scope', None) == scope):
            # Token rotation must not strand an in-flight polling task.
            self.client.set_access_token(values[CONF_SERVICE_TOKEN])
            self.connection = dict(values)
            return
        if getattr(self,'final_follow',None) and not self.final_follow.done():self.final_follow.cancel()
        self.finalizer=None
        self.final_summary={}
        self._configured_scope = scope
        self.connection = dict(values)
        self.client = LottoLabClient(async_get_clientsession(self.hass),
            values[CONF_SERVICE_URL], values[CONF_SERVICE_TOKEN],
            certificate_sha256=values.get(CONF_SERVICE_CERT))
        self.generators={}
        self.generator=self._remote_manager(0)
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
            self._record_health(False, error=self.status)
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
            self._record_health(True, info)
            self.catalog_updated_at = time.monotonic()
            try:await self._resume_finalizer()
            except (LabServiceError,OSError,ValueError):self.final_summary={'connection_status':'unavailable'}
        except (LabServiceError, OSError, ValueError) as exc:
            self.status = exc.code if isinstance(exc,LabServiceError) else 'catalog_storage_error'
            self._record_health(False, error=self.status)
            if self.status == 'reauth_required':
                self.connection_manager.invalidate()

    def legacy_analysis(self, ids=None):
        target = self.owner.history[-1].round+1
        wanted=tuple(self.owner.selected_method_ids if ids is None else ids)
        snapshot = self.owner._prediction_snapshot or {}
        rows=[]
        if snapshot.get('target_round') == target:
            for raw in snapshot.get('recommendations',[]):
                if raw.get('method_id') in wanted:
                    try:
                        item=Recommendation.from_storage(raw)
                        rows.append(Recommendation(item.index,item.method_id,item.label,item.method,
                            item.numbers,'기존 기기에 저장된 번호입니다. 새 Core에서 생성한 기록이 아닙니다.',
                            None,item.details,source='legacy_local',formula_game=item.formula_game))
                    except (ValueError,KeyError,TypeError):
                        continue
        return AnalysisResult(target,target-1,tuple(rows),{
            'selected_method_ids':list(wanted),
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
        # One follower at a time is enough: it refreshes the coordinator, which
        # re-runs every batch that is still outstanding.
        self.retry_tasks={task for task in self.retry_tasks if not task.done()}
        if not self.retry_tasks:
            self.retry_tasks.add(self.hass.async_create_task(self._follow(manager), 'lotto-service-follow'))
        return result

    async def _follow(self, manager):
        try:
            for _ in range(100):
                await asyncio.sleep(2)
                result=await manager.poll()
                if result is None or result.status in ('completed','failed','cancelled'):
                    # A refresh can start the next missing game. Release this
                    # follower's slot first so that job gets its own follower
                    # instead of waiting for the five-minute recovery timer.
                    self.retry_tasks.discard(asyncio.current_task())
                    await self.owner.async_request_refresh()
                    return
        except (LabServiceError,OSError,ValueError):
            self.status='connection_unavailable'
            self.owner.async_update_listeners()
        finally:
            self.retry_tasks.discard(asyncio.current_task())

    async def analysis(self):
        async with self.lock:
            result=await self._batched_analysis()
            if 'post_generation_ticket_set_v1' in self.info.get('capabilities',[]):
                try:await self.finalization_state()
                except (LabServiceError,OSError,ValueError):pass
            return result

    def _merge_batches(self, counts, collected, summaries):
        """Combine every accepted batch result into one ordered analysis."""
        rows=merge_batches(self.owner.selected_method_ids,counts,collected)
        summary=dict(summaries[-1].summary)
        summary['selected_method_ids']=list(self.owner.selected_method_ids)
        summary['games_per_formula']={key:counts[key] for key in summary['selected_method_ids'] if key in counts}
        summary['batch_count']=len(summaries)
        summary['game_shortfall']=shortfalls(summary['selected_method_ids'],counts,rows)
        if summary['game_shortfall']:
            summary['game_shortfall_notice']=(
                '설정한 장수보다 적은 번호가 생성되었습니다. 사용량 제한이나 중간 응답을 확인하세요.'
                '다음 갱신에서 부족한 장수만 다시 요청합니다.'
            )
        else:
            summary.pop('game_shortfall_notice',None)
        return AnalysisResult(summaries[-1].target_round,summaries[-1].based_on_round,rows,summary)

    async def _batched_analysis(self):
        """Ask the service for every outstanding game of each selected formula.

        Each batch owns a durable job slot, so a formula configured for N games
        is satisfied by N single-game batches. A service that already answers one
        request with several games per formula satisfies the remaining batches at
        once, and no further request is sent.
        """
        ids=self.owner.selected_method_ids
        counts=self.owner.formula_game_counts
        collected={}
        summaries=[]
        # Resolve the primary slot after connection setup/recovery. Even the
        # one-game case must merge, since a cached result can contain more games
        # than the newly reduced count. Never discard the durable saved result.
        for index in range(MAX_GAMES_PER_FORMULA):
            batch_ids=next_batch(ids,counts,collected)
            if index and (not batch_ids or not self.client):
                break
            result=(await self._analysis() if index == 0 else
                    await self._analysis(manager=self._remote_manager(index),ids=batch_ids))
            summaries.append(result)
            if result.target_round!=self.owner.history[-1].round+1:
                break  # this batch could not confirm the upcoming round
            fresh=0
            for item in result.recommendations:
                if item.method_id not in batch_ids:
                    continue
                known={row.numbers for row in collected.get(item.method_id,())}
                if item.numbers in known:
                    continue
                collected.setdefault(item.method_id,[]).append(item)
                fresh+=1
            if not fresh:
                # A service that cannot add another distinct game right now will
                # not add one in the next batch either. Later refreshes retry.
                break
        return self._merge_batches(counts,collected,summaries)

    async def _analysis(self, manager=None, ids=None):
        if ids is None:
            ids = self.owner.selected_method_ids
        if self.connection_manager.needs_refresh:
            await self.prepare()
        if not self.client:
            await self.prepare()
        if not self.client:
            return self.legacy_analysis(ids)
        if self.catalog is None or time.monotonic()-self.catalog_updated_at>3600 or self.status in ('connection_unavailable','reauth_required'):
            await self.prepare()
        manager = self.generator if manager is None else manager
        target=self.owner.history[-1].round+1
        options={}
        # Deprecated manual generation rules and JSON overrides are not applied.
        profile=self.owner.saju_profile if METHOD_MYUNGRI_HETU in ids else None
        material=self.material_context(options,profile)
        context_tag=hashlib.sha256(json.dumps([target,ids,material,self.owner._local_generation_nonce]).encode()).hexdigest()
        state=await manager.state()
        if state.get('pending'):
            try:
                result=await manager.poll()
                result=await self._finish_or_schedule(manager,result)
            except LabServiceError as exc:
                pending=state['pending']
                if exc.code!='not_found':
                    self.status='pending_recovery_required'
                    return self._previous_analysis(state,ids)
                if not pending.get('generation_id') and pending.get('context_tag')==context_tag:
                    result=await manager.start(target_round=target,formula_ids=ids,options=options,
                        personal_profile=profile,personal_consent=bool(self.entry.options.get(CONF_PERSONAL_CONSENT)),
                        context_tag=context_tag,mode=pending.get('mode','generate'),
                        source_generation_id=pending.get('source_generation_id'),
                        material_context=material,nonce=self.owner._local_generation_nonce)
                    result=await self._finish_or_schedule(manager,result)
                else:
                    # The service has no record of this job (e.g. its job store was reset).
                    # Nothing was charged; drop the orphan and continue with a normal request.
                    await manager.discard_pending()
            state=await manager.state()
            if state.get('pending'):
                self.status='generating'
                return self._previous_analysis(state,ids)
        previous=state.get('last_result')
        previous_context=state.get('last_context',{})
        if previous and previous_context.get('context_tag')==context_tag:
            self.status='ready'
            self.owner._local_generated_at=datetime.fromisoformat(previous['generated_at'])
            return self.analysis_from_saved(previous,ids,self.owner._local_generation_nonce,self.status)
        if not ids:
            self.status='profile_or_selection_required'
            return self._previous_analysis(state,ids)
        failure=state.get('last_failure') or {}
        if failure.get('context_tag')==context_tag and not retry_due(failure):
            self.status=failure.get('status','failed')
            return self._previous_analysis(state,ids)
        if any(METHODS_BY_ID[x].status=='withdrawn' for x in ids):
            self.status='formula_withdrawn'
            return self._previous_analysis(state,ids)
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
        except (LabServiceError,OSError,ValueError) as exc:
            self.status=exc.code if isinstance(exc,LabServiceError) else 'service_storage_error'
            if self.status=='reauth_required':
                self.connection_manager.invalidate()
        return self._previous_analysis(state,ids)

    def _record_health(self, ok, info=None, error=None):
        """Keep attributes stable between checks: only transitions change `since`."""
        previous = self.health or {}
        now = datetime.now(UTC).isoformat()
        self.health = {
            'ok': ok,
            'error': None if ok else error,
            'since': previous['since'] if previous.get('ok') is ok and previous.get('since') else now,
            'latest_round': (info or {}).get('latest_round', previous.get('latest_round')),
            'core_version': (info or {}).get('core_version', previous.get('core_version')),
        }

    async def health_check(self):
        """Authenticated lightweight check (GET /v1/service) of this installation's connection."""
        async with self.lock:
            if self.client is None:
                self._record_health(False, error=self.status)
                return False
            try:
                if self.connection_manager.needs_refresh:
                    await self.connection_manager.ensure_enrolled(async_get_clientsession(self.hass))
                    self._configure_connection(self.connection_manager.values)
                info = await self.client.async_service_info()
            except (LabServiceError, OSError, ValueError) as exc:
                code = exc.code if isinstance(exc, LabServiceError) else 'health_check_failed'
                self._record_health(False, error=code)
                if code == 'reauth_required':
                    self.status = code
                    self.connection_manager.invalidate()
                elif self.status == 'ready' and code in ('connection_unavailable', 'service_unavailable'):
                    self.status = code
                return False
            self.info = info
            self._record_health(True, info)
            return True

    def watch_member_link(self, grant):
        """Complete an approved member link in the background; HA needs no second confirmation."""
        if self.member_task is not None and not self.member_task.done():
            self.member_task.cancel()
        link = {'grant': grant, 'status': 'pending'}
        self.member_link = link
        self.member_task = self.hass.async_create_background_task(
            self._complete_member_link(link), 'lotto-member-link')
        return link

    async def _complete_member_link(self, link):
        session = async_get_clientsession(self.hass)
        grant = link['grant']
        while True:
            await asyncio.sleep(max(1.0, grant['next_poll'] - time.time()))
            try:
                tokens = await poll_member_link(session, grant)
            except LabServiceError as exc:
                if exc.code in ('authorization_pending', 'slow_down', 'member_service_unavailable'):
                    continue  # poll() raises expired_token once the grant lifetime ends
                link['status'] = exc.code
                self.owner.async_update_listeners()
                return
            try:
                await self.connection_manager.store.async_save(
                    state_from_tokens(tokens, self.connection_manager.state))
            except (OSError, ValueError):
                link['status'] = 'member_storage_error'
                self.owner.async_update_listeners()
                return
            link['status'] = 'linked'
            self.owner.async_update_listeners()
            # Separate task: unloading this entry must not cancel the reload itself.
            self.hass.async_create_task(self.hass.config_entries.async_reload(self.entry.entry_id))
            return

    async def generation_retry_due(self):
        """True when a stored server-side generation failure is ready for an automatic retry."""
        if self.generators is None:
            return False
        for manager in list(self.generators.values()):
            try:
                state=await manager.state()
            except (LabServiceError,OSError,ValueError):
                return False
            if retry_due(state.get('last_failure')):
                return True
        return False

    def _previous_analysis(self,state,ids=None):
        old=state.get('last_result')
        target=self.owner.history[-1].round+1
        wanted=tuple(self.owner.selected_method_ids if ids is None else ids)
        if old and old['target_round']==target:
            return self.analysis_from_saved(old,wanted,
                self.owner._local_generation_nonce,self.status)
        return self.legacy_analysis(wanted)

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
        if self.member_task and not self.member_task.done():
            self.member_task.cancel()
            await asyncio.gather(self.member_task,return_exceptions=True)
        if self.final_follow and not self.final_follow.done():
            self.final_follow.cancel()
            await asyncio.gather(self.final_follow,return_exceptions=True)
        followups=[task for task in self.retry_tasks if not task.done()]
        for task in followups:
            task.cancel()
        if followups:
            await asyncio.gather(*followups,return_exceptions=True)
        self.retry_tasks.clear()
