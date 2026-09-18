"""Private per-installation connection state; never a user options form.

Existing operator-provisioned identities are migrated without changing token,
origin or generation journal. New installations require explicit member approval at the fixed service
origin. No shared credential is shipped.
"""
from __future__ import annotations
import asyncio
import copy
import hashlib
import re
import secrets
import time
import uuid
import aiohttp
from .const import CONF_SERVICE_URL, CONF_SERVICE_TOKEN, CONF_SERVICE_CERT
from .lab_client import LabServiceError, service_origin, CLIENT_USER_AGENT

RETIRED_SERVICE_ORIGIN = "https://lottolab.toiss.kr"
DEFAULT_SERVICE_URL = "https://lotto.formulab.kr"
CONNECTION_KEYS = (CONF_SERVICE_URL, CONF_SERVICE_TOKEN, CONF_SERVICE_CERT)
REMOVED_OPTIONS = frozenset(("generation_rules", "formula_options", "_member_link"))


def connection_values(raw):
    if not isinstance(raw, dict):
        raise ValueError("invalid_managed_connection")
    origin = service_origin(raw.get(CONF_SERVICE_URL, ""))
    token = raw.get(CONF_SERVICE_TOKEN, "")
    if not isinstance(token, str) or not 16 <= len(token) <= 4096 or re.search(r"[\s\x00-\x1f]", token):
        raise ValueError("invalid_managed_credential")
    pin = raw.get(CONF_SERVICE_CERT, "") or ""
    if not isinstance(pin, str):
        raise ValueError("invalid_managed_certificate")
    pin = pin.replace(":", "").lower()
    if pin and not re.fullmatch(r"[0-9a-f]{64}", pin):
        raise ValueError("invalid_managed_certificate")
    return {CONF_SERVICE_URL: origin, CONF_SERVICE_TOKEN: token, CONF_SERVICE_CERT: pin}


def without_user_connection(raw):
    return {k: v for k, v in dict(raw).items() if k not in CONNECTION_KEYS and k not in REMOVED_OPTIONS}


def _migrate_retired_origin(saved):
    """Rewrite the retired service origin in place, pinning the old journal scope.

    Tokens, device identity and records are preserved; only the endpoint moves.
    Returns True when the stored state changed and must be persisted.
    """
    if not isinstance(saved, dict):
        return False
    creds = saved.get('credentials')
    if not isinstance(creds, dict) or creds.get(CONF_SERVICE_URL) != RETIRED_SERVICE_ORIGIN:
        return False
    if not saved.get('journal_scope'):
        token = creds.get(CONF_SERVICE_TOKEN, '')
        saved['journal_scope'] = hashlib.sha256(
            (RETIRED_SERVICE_ORIGIN + '\0' + str(token)).encode()).hexdigest()[:24]
    creds[CONF_SERVICE_URL] = DEFAULT_SERVICE_URL
    return True


class ManagedConnection:
    def __init__(self, store):
        self.store = store
        self.state = None
        self.retry_at = 0.0
        self._refresh_lock = asyncio.Lock()

    @property
    def values(self):
        return dict(self.state["credentials"]) if self.state else {}

    async def load(self, legacy=None):
        if self.state is not None:
            return
        saved = await self.store.async_load()
        if saved is not None:
            if not isinstance(saved, dict) or saved.get("version") != 1 or saved.get("source") not in ("operator", "automatic", "member"):
                raise ValueError("invalid_managed_storage")
            connection_values(saved.get("credentials"))
            if saved["source"] == "automatic" and not re.fullmatch(r"[0-9a-f]{32}", str(saved.get("installation_id", ""))):
                raise ValueError("invalid_installation_id")
            if _migrate_retired_origin(saved):
                connection_values(saved.get("credentials"))
                try:
                    await self.store.async_save(saved)
                except OSError:
                    self.state = None
                    raise
            self.state = saved
            return
        if legacy and legacy.get('_member_link'):
            saved=copy.deepcopy(legacy['_member_link'])
            if saved.get('source')!='member':raise ValueError('invalid_member_bootstrap')
            connection_values(saved.get('credentials'))
        elif legacy and legacy.get(CONF_SERVICE_URL) and legacy.get(CONF_SERVICE_TOKEN):
            saved = {"version": 1, "source": "operator", "credentials": connection_values(legacy), "enrolled": True}
        else:
            saved = {"version": 1, "source": "automatic", "installation_id": uuid.uuid4().hex,
                     "credentials": {CONF_SERVICE_URL: DEFAULT_SERVICE_URL,
                                     CONF_SERVICE_TOKEN: secrets.token_urlsafe(32), CONF_SERVICE_CERT: ""},
                     "enrolled": False}
        # Persist the exact identity before network use. A timeout cannot create a
        # second identity, and a failed save never removes the legacy credential.
        if _migrate_retired_origin(saved):
            connection_values(saved.get("credentials"))
        await self.store.async_save(saved)
        self.state = saved

    def invalidate(self):
        if self.state and self.state['source']=='member':
            self.state['access_expires_at']=0
        elif self.state and self.state['source']=='automatic':
            self.state['enrolled']=False

    @property
    def journal_scope(self):
        if self.state and self.state.get('journal_scope'):
            return self.state['journal_scope']
        import hashlib
        values=self.values
        return hashlib.sha256((values.get(CONF_SERVICE_URL,'')+'\0'+values.get(CONF_SERVICE_TOKEN,'')).encode()).hexdigest()[:24]

    @property
    def context_secret(self):
        return (self.state or {}).get('context_secret') or self.values.get(CONF_SERVICE_TOKEN,'')

    @property
    def needs_refresh(self):
        return bool(self.state and self.state['source']=='member' and self.state.get('access_expires_at',0)<time.time()+60)

    async def ensure_enrolled(self, session):
        # Concurrent sensor refreshes share one token rotation and persisted result.
        async with self._refresh_lock:
            await self._ensure_enrolled(session)

    async def _ensure_enrolled(self, session):
        if not self.state:
            raise LabServiceError('member_link_required')
        if self.state['source']=='operator':
            return  # Explicitly operator-provisioned identity, not anonymous enrollment.
        if self.state['source']!='member':
            raise LabServiceError('member_link_required')
        if self.state.get('link_required'):
            raise LabServiceError('member_link_required')
        if not self.needs_refresh:
            return
        if time.monotonic()<self.retry_at:
            raise LabServiceError('member_connection_pending')
        self.retry_at=time.monotonic()+30
        from .member_link import request,valid_tokens,CLIENT_ID
        saved=copy.deepcopy(self.state)
        if not saved.get('pending_rotation'):
            saved['pending_rotation']=secrets.token_urlsafe(24)
            await self.store.async_save(saved);self.state=saved
        try:
            tokens=valid_tokens(await request(session,'/oauth/token',{
                'client_id':CLIENT_ID,'grant_type':'refresh_token',
                'refresh_token':saved['refresh_token'],'rotation_id':saved['pending_rotation']}))
        except LabServiceError as exc:
            if exc.code=='invalid_grant':
                saved['link_required']=True;await self.store.async_save(saved);self.state=saved
                raise LabServiceError('member_link_required') from exc
            raise
        if tokens['device_id']!=saved['device_id']:
            raise LabServiceError('invalid_member_response')
        saved['credentials'][CONF_SERVICE_TOKEN]=tokens['access_token']
        saved['refresh_token']=tokens['refresh_token']
        saved['access_expires_at']=time.time()+tokens['expires_in']
        saved.pop('pending_rotation',None)
        await self.store.async_save(saved);self.state=saved;self.retry_at=0
