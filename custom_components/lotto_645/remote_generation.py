"""Durable remote generation state, independent of the wallet and HA lifecycle.

A Store-compatible object supplies async_load/async_save. This class is ready
for coordinator integration but is NOT activated in v1.21.0 automatically.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, UTC
from hashlib import sha256
import json
from typing import Any, Protocol
from uuid import uuid4

from .lab_client import LottoLabClient, LabServiceError
from .service_contract import Generation, method_ids, positive


class Store(Protocol):
    async def async_load(self) -> dict | None: ...
    async def async_save(self, value: dict) -> None: ...


class RemoteGeneration:
    """One pending operation per HA entry. No core fallback or silent replacement."""
    def __init__(self, client: LottoLabClient, store: Store):
        self.client = client
        self.store = store
        self._lock = asyncio.Lock()
        self._state: dict | None = None

    async def _load(self):
        if self._state is None:
            raw = await self.store.async_load()
            if raw is None:
                raw = {"schema": 1, "pending": None, "last_result": None}
            if (not isinstance(raw, dict) or raw.get("schema") != 1
                    or raw.get("pending") is not None and not isinstance(raw.get("pending"), dict)
                    or raw.get("last_result") is not None and not isinstance(raw.get("last_result"), dict)):
                raise LabServiceError("generation_storage_invalid")
            self._state = deepcopy(raw)

    async def _save(self, value: dict):
        # A failed disk write must not publish a result or lose the retry key.
        await self.store.async_save(deepcopy(value))
        self._state = value

    async def start(self, *, target_round: int, formula_ids, options: dict | None = None,
                    personal_profile: dict | None = None, personal_consent: bool = False) -> Generation:
        target, ids = positive(target_round), method_ids(formula_ids)
        public_options = deepcopy(options or {})
        if personal_profile is not None and not personal_consent:
            raise LabServiceError("personal_consent_required")
        public_context = {"target_round": target, "formula_ids": list(ids), "options": public_options,
                          "requires_personal_input": personal_profile is not None}
        fingerprint = sha256(json.dumps(public_context, sort_keys=True, allow_nan=False).encode()).hexdigest()
        async with self._lock:
            await self._load()
            current = self._state["pending"]
            if current is not None:
                if current.get("context_hash") != fingerprint:
                    raise LabServiceError("pending_generation_conflict")
                # Do not resubmit a different personal profile under a pending key.
                # Once accepted, poll by generation ID. Before acceptance, the caller
                # must explicitly retry with its original profile or resolve the key
                # through the service; no profile is persisted here.
                if current.get("generation_id"):
                    return await self._poll(current)
                if current.get("requires_personal_input"):
                    raise LabServiceError("personal_request_recovery_required")
            else:
                current = {**public_context, "request_key": str(uuid4()), "generation_id": None,
                           "context_hash": fingerprint, "created_at": datetime.now(UTC).isoformat()}
                await self._save({**self._state, "pending": current})
            result = await self.client.async_generate(
                request_key=current["request_key"], target_round=target, formula_ids=ids,
                options=public_options, personal_profile=personal_profile, personal_consent=personal_consent)
            return await self._accept(result, current)

    async def poll(self) -> Generation | None:
        async with self._lock:
            await self._load()
            pending = self._state["pending"]
            if pending is None:
                return None
            if not pending.get("generation_id"):
                raise LabServiceError("request_not_acknowledged")
            return await self._poll(pending)

    async def _poll(self, pending: dict) -> Generation:
        result = await self.client.async_get_generation(
            pending["generation_id"], request_key=pending["request_key"], target_round=pending["target_round"],
            formula_ids=pending["formula_ids"])
        return await self._accept(result, pending)

    async def _accept(self, result: Generation, pending: dict) -> Generation:
        updated = deepcopy(self._state)
        if result.status == "completed":
            updated.update(pending=None, last_result=asdict(result))
        elif result.status in ("failed", "cancelled"):
            updated.update(pending=None, last_failure={"generation_id": result.generation_id, "status": result.status})
        else:
            updated["pending"] = {**pending, "generation_id": result.generation_id}
        await self._save(updated)
        return result

    async def saved_result(self) -> dict | None:
        async with self._lock:
            await self._load()
            return deepcopy(self._state["last_result"])
