"""Private per-installation connection state; never a user options form.

Existing operator-provisioned identities are migrated without changing token,
origin or generation journal. New installations enroll against the fixed service
origin when that operator endpoint is available. No shared credential is shipped.
"""
from __future__ import annotations
import asyncio
import copy
import re
import secrets
import time
import uuid
import aiohttp
from .const import CONF_SERVICE_URL, CONF_SERVICE_TOKEN, CONF_SERVICE_CERT
from .lab_client import LabServiceError, service_origin, CLIENT_USER_AGENT

DEFAULT_SERVICE_URL = "https://lottolab.toiss.kr"
CONNECTION_KEYS = (CONF_SERVICE_URL, CONF_SERVICE_TOKEN, CONF_SERVICE_CERT)
REMOVED_OPTIONS = frozenset(("generation_rules", "formula_options"))


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


class ManagedConnection:
    def __init__(self, store):
        self.store = store
        self.state = None
        self.retry_at = 0.0

    @property
    def values(self):
        return dict(self.state["credentials"]) if self.state else {}

    async def load(self, legacy=None):
        if self.state is not None:
            return
        saved = await self.store.async_load()
        if saved is not None:
            if not isinstance(saved, dict) or saved.get("version") != 1 or saved.get("source") not in ("operator", "automatic"):
                raise ValueError("invalid_managed_storage")
            connection_values(saved.get("credentials"))
            if saved["source"] == "automatic" and not re.fullmatch(r"[0-9a-f]{32}", str(saved.get("installation_id", ""))):
                raise ValueError("invalid_installation_id")
            self.state = saved
            return
        if legacy and legacy.get(CONF_SERVICE_URL) and legacy.get(CONF_SERVICE_TOKEN):
            saved = {"version": 1, "source": "operator", "credentials": connection_values(legacy), "enrolled": True}
        else:
            saved = {"version": 1, "source": "automatic", "installation_id": uuid.uuid4().hex,
                     "credentials": {CONF_SERVICE_URL: DEFAULT_SERVICE_URL,
                                     CONF_SERVICE_TOKEN: secrets.token_urlsafe(32), CONF_SERVICE_CERT: ""},
                     "enrolled": False}
        # Persist the exact identity before network use. A timeout cannot create a
        # second identity, and a failed save never removes the legacy credential.
        await self.store.async_save(saved)
        self.state = saved

    def invalidate(self):
        if self.state and self.state["source"] == "automatic":
            self.state["enrolled"] = False

    async def ensure_enrolled(self, session):
        if not self.state:
            raise LabServiceError("managed_connection_pending")
        if self.state.get("enrolled"):
            return
        if time.monotonic() < self.retry_at:
            raise LabServiceError("managed_connection_pending")
        self.retry_at = time.monotonic() + 300
        values = self.values
        origin = values[CONF_SERVICE_URL]
        # An automatic enrollment destination is fixed by the application, not
        # received from a QR, redirect, member input or discovery advertisement.
        if origin != DEFAULT_SERVICE_URL:
            raise LabServiceError("untrusted_enrollment_origin")
        payload = {"installation_id": self.state["installation_id"], "credential": values[CONF_SERVICE_TOKEN]}
        try:
            async with session.post(origin + "/v1/ha/installations", json=payload,
                    headers={"Accept": "application/json", "User-Agent": CLIENT_USER_AGENT}, allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=10), ssl=True) as response:
                if response.status == 429:
                    raise LabServiceError("managed_connection_pending")
                if response.status in (401, 403, 409):
                    raise LabServiceError("operator_attention_required")
                if response.status not in (200, 201) or response.content_type != "application/json":
                    raise LabServiceError("managed_connection_pending")
                chunks = []; size = 0
                async for chunk in response.content.iter_chunked(1024):
                    size += len(chunk)
                    if size > 8192:
                        raise LabServiceError("invalid_enrollment_response")
                    chunks.append(chunk)
                import json
                raw = json.loads(b"".join(chunks))
                if (not isinstance(raw, dict) or raw.get("contract_version") != 1
                        or raw.get("installation_id") != self.state["installation_id"]
                        or raw.get("enrolled") is not True):
                    raise LabServiceError("invalid_enrollment_response")
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
            raise LabServiceError("managed_connection_pending") from exc
        saved = copy.deepcopy(self.state)
        saved["enrolled"] = True
        await self.store.async_save(saved)
        self.state = saved
        self.retry_at = 0.0
