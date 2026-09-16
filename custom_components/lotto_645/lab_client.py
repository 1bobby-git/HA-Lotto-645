"""Explicit asynchronous service client; never downloads or imports core code.

This transport has no HA/runtime side effects. The coordinator must persist a
request key BEFORE POST, retain it across timeouts/restarts, and commit a final
validated result before announcing completion. No automatic generation retry
with a new key is performed here.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json
import re
from urllib.parse import urlsplit
from typing import Any

import aiohttp

from .const import VERSION

CLIENT_USER_AGENT = f"HA-Lotto-645/{VERSION} (+https://github.com/1bobby-git/HA-Lotto-645)"

from .service_contract import Catalog, ContractError, Generation, identifier, method_ids, positive

MAX_RESPONSE_BYTES = 2_000_000
MAX_REQUEST_BYTES = 256_000


class LabServiceError(Exception):
    """Safe error; raw response, token and URL credentials are never attached."""
    def __init__(self, code: str, *, retry_after: int | None = None):
        super().__init__(code)
        self.code = code
        self.retry_after = retry_after


def service_origin(value: str, *, allow_loopback_http: bool = False) -> str:
    if not isinstance(value, str) or len(value) > 1000 or any(c.isspace() for c in value):
        raise ValueError("invalid_service_origin")
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid_service_origin") from exc
    if not host or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("invalid_service_origin")
    permitted_http = False
    if allow_loopback_http and parsed.scheme == "http":
        try:
            permitted_http = ipaddress.ip_address(host).is_loopback
        except ValueError:
            permitted_http = host == "localhost"
    if parsed.scheme != "https" and not permitted_http:
        raise ValueError("https_required")
    # The origin is administrator-configured, never obtained from a QR or a member post.
    return f"{parsed.scheme}://{parsed.netloc}"


class LottoLabClient:
    def __init__(self, session: aiohttp.ClientSession, base_url: str, access_token: str,
                 *, allow_loopback_http: bool = False, timeout: float = 15.0, certificate_sha256: str | None = None):
        self._session = session
        self._origin = service_origin(base_url, allow_loopback_http=allow_loopback_http)
        self._token = self._valid_token(access_token)
        if not 0 < timeout <= 120:
            raise ValueError("invalid_timeout")
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._ssl = True
        if certificate_sha256:
            digest = certificate_sha256.replace(":", "").lower()
            if not re.fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("invalid_certificate_fingerprint")
            self._ssl = aiohttp.Fingerprint(bytes.fromhex(digest))

    @staticmethod
    def _valid_token(value: Any) -> str:
        if not isinstance(value, str) or not 16 <= len(value) <= 4096 or re.search(r"[\s\x00-\x1f]", value):
            raise ValueError("invalid_service_token")
        return value

    def set_access_token(self, value: str) -> None:
        self._token = self._valid_token(value)

    async def _request(self, method: str, path: str, *, body: dict | None = None, request_key: str | None = None):
        headers = {"Authorization": f"Bearer {self._token}", "Accept": "application/json", "User-Agent": CLIENT_USER_AGENT}
        if request_key:
            headers["Idempotency-Key"] = identifier(request_key)
        if body is not None:
            try:
                serialized = json.dumps(body, allow_nan=False)
            except (ValueError, TypeError) as exc:
                raise LabServiceError("invalid_request") from exc
            if len(serialized.encode()) > MAX_REQUEST_BYTES:
                raise LabServiceError("request_too_large")
        try:
            async with self._session.request(method, self._origin + path, json=body, headers=headers,
                                             timeout=self._timeout, allow_redirects=False, ssl=self._ssl) as response:
                retry = response.headers.get("Retry-After", "")
                retry_after = min(int(retry), 3600) if retry.isdecimal() and len(retry) < 9 else None
                code = {401: "reauth_required", 403: "permission_denied", 404: "not_found",
                        409: "request_conflict", 422: "invalid_generation_request", 429: "usage_limited"}.get(response.status)
                if code:
                    raise LabServiceError(code, retry_after=retry_after)
                if 300 <= response.status < 400:
                    raise LabServiceError("redirect_refused")
                if response.status >= 500:
                    raise LabServiceError("service_unavailable", retry_after=retry_after)
                if response.status not in (200, 201, 202):
                    raise LabServiceError("unexpected_status")
                if response.content_type != "application/json":
                    raise LabServiceError("invalid_response_type")
                if response.content_length is not None and response.content_length > MAX_RESPONSE_BYTES:
                    raise LabServiceError("response_too_large")
                chunks, size = [], 0
                async for part in response.content.iter_chunked(65536):
                    size += len(part)
                    if size > MAX_RESPONSE_BYTES:
                        raise LabServiceError("response_too_large")
                    chunks.append(part)
                try:
                    return json.loads(b"".join(chunks), parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                except (ValueError, UnicodeError, RecursionError) as exc:
                    raise LabServiceError("invalid_response_json") from exc
        except LabServiceError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
            # Timeout may mean the server already committed the generation.
            # Preserve the caller's original key rather than generating again.
            raise LabServiceError("connection_unavailable") from exc

    async def async_catalog(self) -> Catalog:
        try:
            return Catalog.parse(await self._request("GET", "/v1/formulas"))
        except (ContractError, ValueError, TypeError) as exc:
            raise LabServiceError("invalid_catalog") from exc

    async def async_service_info(self) -> dict:
        value = await self._request("GET", "/v1/service")
        if not isinstance(value, dict) or value.get("contract_version") != 1:
            raise LabServiceError("unsupported_service")
        identifier(value.get("device_id"))
        return value

    async def async_validate(self, formula_ids, options=None, personal_profile=None, personal_consent=False):
        body = {"formula_ids": list(formula_ids), "options": options or {}}
        if personal_profile is not None:
            if personal_consent is not True:
                raise LabServiceError("personal_consent_required")
            body.update(personal_profile=personal_profile, personal_consent=True)
        value = await self._request("POST", "/v1/validate", body=body)
        if value.get("valid") is not True:
            raise LabServiceError("invalid_options")
        return value

    async def async_get_by_key(self, *, request_key, target_round, formula_ids):
        key = identifier(request_key)
        raw = await self._request("GET", f"/v1/generations/by-key/{key}")
        return self._parse_generation(raw, key, positive(target_round), method_ids(formula_ids))

    async def async_generate(self, *, request_key: str, target_round: int, formula_ids,
                             options: dict | None = None, personal_profile: dict | None = None,
                             personal_consent: bool = False, mode: str = "generate",
                             source_generation_id: str | None = None) -> Generation:
        key, target, ids = identifier(request_key), positive(target_round), method_ids(formula_ids)
        if options is not None and not isinstance(options, dict):
            raise LabServiceError("invalid_options")
        if personal_profile is not None and (not personal_consent or not isinstance(personal_profile, dict)):
            raise LabServiceError("personal_consent_required")
        body = {"contract_version": 1, "request_key": key, "target_round": target,
                "formula_ids": list(ids), "options": options or {}, "mode": mode}
        if source_generation_id:
            body["source_generation_id"] = identifier(source_generation_id)
        if personal_profile is not None:
            body["personal_profile"] = personal_profile
            body["personal_consent"] = True
        raw = await self._request("POST", "/v1/generations", body=body, request_key=key)
        return self._parse_generation(raw, key, target, ids)

    async def async_get_generation(self, generation_id: str, *, request_key: str,
                                   target_round: int, formula_ids) -> Generation:
        gid = identifier(generation_id)
        raw = await self._request("GET", f"/v1/generations/{gid}")
        return self._parse_generation(raw, identifier(request_key), positive(target_round), method_ids(formula_ids), gid)

    async def async_cancel_generation(self, generation_id: str, *, request_key: str,
                                      target_round: int, formula_ids) -> Generation:
        gid = identifier(generation_id)
        raw = await self._request("POST", f"/v1/generations/{gid}/cancel", body={}, request_key=request_key)
        return self._parse_generation(raw, identifier(request_key), positive(target_round), method_ids(formula_ids), gid)

    @staticmethod
    def _parse_generation(raw, key, target, ids, gid=None):
        try:
            return Generation.parse(raw, expected_key=key, expected_target=target,
                                    requested_ids=ids, expected_generation_id=gid)
        except (ContractError, TypeError, ValueError) as exc:
            raise LabServiceError("invalid_generation_response") from exc
