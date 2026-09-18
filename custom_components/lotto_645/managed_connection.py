"""Managed per-installation connection state; no user account is required.

Existing operator-provisioned identities remain valid. New and former member-linked
installations use bounded anonymous enrollment at the fixed Formulab Lotto origin.
No shared service credential is shipped in the integration.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
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


def _scope(values):
    return hashlib.sha256(
        (values.get(CONF_SERVICE_URL, "") + "\0" + values.get(CONF_SERVICE_TOKEN, "")).encode()
    ).hexdigest()[:24]


def _migrate_retired_origin(saved):
    """Move the retired hostname without changing an automatic/operator identity."""
    if not isinstance(saved, dict):
        return False
    creds = saved.get("credentials")
    if not isinstance(creds, dict) or creds.get(CONF_SERVICE_URL) != RETIRED_SERVICE_ORIGIN:
        return False
    if not saved.get("journal_scope"):
        saved["journal_scope"] = _scope(creds)
    creds[CONF_SERVICE_URL] = DEFAULT_SERVICE_URL
    return True


def _member_to_automatic(saved):
    """Replace the temporary member grant with an installation-local identity."""
    if not isinstance(saved, dict) or saved.get("source") != "member":
        return False
    values = connection_values(saved.get("credentials"))
    journal_scope = saved.get("journal_scope") or _scope(values)
    context_secret = saved.get("context_secret") or values[CONF_SERVICE_TOKEN] or secrets.token_urlsafe(32)
    saved.clear()
    saved.update({
        "version": 1,
        "source": "automatic",
        "installation_id": uuid.uuid4().hex,
        "credentials": {
            CONF_SERVICE_URL: DEFAULT_SERVICE_URL,
            CONF_SERVICE_TOKEN: secrets.token_urlsafe(32),
            CONF_SERVICE_CERT: "",
        },
        "enrolled": False,
        "expires_at": 0,
        "journal_scope": journal_scope,
        "context_secret": context_secret,
    })
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
            if not isinstance(saved, dict) or saved.get("version") != 1 or saved.get("source") not in (
                "operator", "automatic", "member"
            ):
                raise ValueError("invalid_managed_storage")
            connection_values(saved.get("credentials"))
            changed = _member_to_automatic(saved)
            changed = _migrate_retired_origin(saved) or changed
            if saved["source"] == "automatic":
                iid = str(saved.get("installation_id", ""))
                if not re.fullmatch(r"[0-9a-f]{32}", iid):
                    raise ValueError("invalid_installation_id")
                saved.setdefault("expires_at", 0)
            if changed:
                connection_values(saved.get("credentials"))
                try:
                    await self.store.async_save(saved)
                except OSError:
                    self.state = None
                    raise
            self.state = saved
            return

        if legacy and legacy.get("_member_link"):
            saved = copy.deepcopy(legacy["_member_link"])
            if saved.get("source") != "member":
                raise ValueError("invalid_member_bootstrap")
            connection_values(saved.get("credentials"))
            _member_to_automatic(saved)
        elif legacy and legacy.get(CONF_SERVICE_URL) and legacy.get(CONF_SERVICE_TOKEN):
            saved = {
                "version": 1,
                "source": "operator",
                "credentials": connection_values(legacy),
                "enrolled": True,
            }
        else:
            saved = {
                "version": 1,
                "source": "automatic",
                "installation_id": uuid.uuid4().hex,
                "credentials": {
                    CONF_SERVICE_URL: DEFAULT_SERVICE_URL,
                    CONF_SERVICE_TOKEN: secrets.token_urlsafe(32),
                    CONF_SERVICE_CERT: "",
                },
                "enrolled": False,
                "expires_at": 0,
            }
        if _migrate_retired_origin(saved):
            connection_values(saved.get("credentials"))
        await self.store.async_save(saved)
        self.state = saved

    def invalidate(self):
        if self.state and self.state["source"] == "automatic":
            self.state["enrolled"] = False
            self.state["expires_at"] = 0

    @property
    def journal_scope(self):
        if self.state and self.state.get("journal_scope"):
            return self.state["journal_scope"]
        return _scope(self.values)

    @property
    def context_secret(self):
        return (self.state or {}).get("context_secret") or self.values.get(CONF_SERVICE_TOKEN, "")

    @property
    def needs_refresh(self):
        if not self.state or self.state["source"] != "automatic":
            return False
        return not self.state.get("enrolled") or float(self.state.get("expires_at") or 0) < time.time() + 7 * 86400

    async def ensure_enrolled(self, session):
        async with self._refresh_lock:
            await self._ensure_enrolled(session)

    async def _ensure_enrolled(self, session):
        if not self.state:
            raise LabServiceError("managed_connection_missing")
        if self.state["source"] == "operator":
            return
        if self.state["source"] != "automatic":
            raise LabServiceError("managed_connection_invalid")
        if not self.needs_refresh:
            return
        if time.monotonic() < self.retry_at:
            raise LabServiceError("connection_pending")
        self.retry_at = time.monotonic() + 30

        saved = copy.deepcopy(self.state)
        values = connection_values(saved["credentials"])
        body = {
            "installation_id": saved["installation_id"],
            "credential": values[CONF_SERVICE_TOKEN],
        }
        try:
            async with session.post(
                values[CONF_SERVICE_URL] + "/v1/ha/installations",
                json=body,
                headers={"Accept": "application/json", "User-Agent": CLIENT_USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=False,
                ssl=True,
            ) as response:
                if response.content_type != "application/json":
                    raise LabServiceError("invalid_enrollment_response")
                parts, size = [], 0
                async for part in response.content.iter_chunked(2048):
                    size += len(part)
                    if size > 16384:
                        raise LabServiceError("invalid_enrollment_response")
                    parts.append(part)
                try:
                    payload = json.loads(b"".join(parts))
                except (ValueError, UnicodeError) as exc:
                    raise LabServiceError("invalid_enrollment_response") from exc
                if response.status == 429:
                    raise LabServiceError("usage_limited")
                if response.status in (403, 409):
                    raise LabServiceError(payload.get("error") or "automatic_connection_refused")
                if response.status >= 500:
                    raise LabServiceError(payload.get("error") or "service_unavailable")
                if response.status not in (200, 201):
                    raise LabServiceError("unexpected_enrollment_status")
        except LabServiceError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            raise LabServiceError("connection_unavailable") from exc

        expires = payload.get("expires_at")
        expected_device = "ha-" + saved["installation_id"]
        if (
            payload.get("contract_version") != 1
            or payload.get("installation_id") != saved["installation_id"]
            or payload.get("device_id") != expected_device
            or payload.get("enrolled") is not True
            or not isinstance(expires, (int, float))
            or expires < time.time() + 3600
        ):
            raise LabServiceError("invalid_enrollment_response")

        saved["enrolled"] = True
        saved["expires_at"] = float(expires)
        await self.store.async_save(saved)
        self.state = saved
        self.retry_at = 0.0
