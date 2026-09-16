"""Public, calculation-free Lotto Lab service contract.

This module can be imported without HA or the private core. It intentionally
constructs fresh allowlisted values; upstream ``details``/``summary`` and
private research metadata are not retained.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
from typing import Any, Mapping

CONTRACT_VERSION = 1
_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,127}\Z")
_STATES = frozenset(("queued", "running", "completed", "failed", "cancelled"))


class ContractError(ValueError):
    """A safe, non-echoing protocol error."""


def identifier(value: Any) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise ContractError("invalid_identifier")
    return value


def text(value: Any, limit: int = 1000) -> str:
    if not isinstance(value, str) or len(value) > limit or "\x00" in value:
        raise ContractError("invalid_text")
    return value


def positive(value: Any) -> int:
    if type(value) is not int or value < 1 or value > 999999:
        raise ContractError("invalid_round")
    return value


def timestamp(value: Any) -> str:
    try:
        parsed = datetime.fromisoformat(text(value, 64))
    except (ValueError, TypeError) as exc:
        raise ContractError("invalid_timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ContractError("timezone_required")
    return parsed.isoformat()


def numbers(value: Any) -> tuple[int, ...]:
    if (not isinstance(value, (list, tuple)) or len(value) != 6
            or any(type(n) is not int or not 1 <= n <= 45 for n in value)
            or len(set(value)) != 6):
        raise ContractError("invalid_numbers")
    return tuple(sorted(value))


def method_ids(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not 1 <= len(value) <= 128:
        raise ContractError("invalid_methods")
    result = tuple(identifier(v) for v in value)
    if len(set(result)) != len(result):
        raise ContractError("duplicate_methods")
    return result


def _schema(value: Any) -> dict:
    """Accept a bounded JSON schema, never code/URLs or remote references."""
    if not isinstance(value, dict) or len(json.dumps(value, ensure_ascii=False)) > 32000:
        raise ContractError("invalid_options_schema")
    def visit(v, depth=0):
        if depth > 10:
            raise ContractError("schema_depth")
        if isinstance(v, dict):
            if len(v) > 128:
                raise ContractError("schema_width")
            if any(k in v for k in ("$ref", "$dynamicRef", "script", "html", "javascript")):
                raise ContractError("unsupported_schema")
            for k, item in v.items():
                text(k, 128); visit(item, depth + 1)
        elif isinstance(v, list):
            if len(v) > 256:
                raise ContractError("schema_width")
            for item in v:
                visit(item, depth + 1)
        elif v is not None and type(v) not in (str, int, float, bool):
            raise ContractError("invalid_schema_type")
    visit(value)
    # Reject NaN/Infinity even though Python's JSON decoder tolerates them.
    return json.loads(json.dumps(value, allow_nan=False))


@dataclass(frozen=True)
class Formula:
    formula_id: str
    formula_version: str
    name: str
    category: str
    public_summary: str
    status: str
    requires_personal_profile: bool
    options_schema: dict
    min_history: int


@dataclass(frozen=True)
class Catalog:
    core_version: str
    methods: tuple[Formula, ...]
    default_method_ids: tuple[str, ...]

    @classmethod
    def parse(cls, raw: Any) -> "Catalog":
        if not isinstance(raw, dict) or type(raw.get("contract_version")) is not int or raw["contract_version"] != CONTRACT_VERSION:
            raise ContractError("unsupported_contract")
        entries = raw.get("methods")
        if not isinstance(entries, list) or not 1 <= len(entries) <= 128:
            raise ContractError("invalid_catalog")
        rows = []
        for row in entries:
            if not isinstance(row, dict):
                raise ContractError("invalid_formula")
            status = row.get("status")
            personal = row.get("requires_personal_profile")
            if status not in ("active", "deprecated", "withdrawn") or type(personal) is not bool:
                raise ContractError("invalid_formula_state")
            rows.append(Formula(identifier(row.get("formula_id")), identifier(row.get("formula_version")),
                                text(row.get("name"), 180), text(row.get("category"), 180),
                                text(row.get("public_summary")), status, personal,
                                _schema(row.get("options_schema")), positive(row.get("min_history"))))
        ids = {r.formula_id for r in rows}
        defaults = method_ids(raw.get("default_method_ids"))
        if len(ids) != len(rows) or not set(defaults) <= ids:
            raise ContractError("invalid_catalog_ids")
        return cls(identifier(raw.get("core_version")), tuple(rows), defaults)


@dataclass(frozen=True)
class PublicGame:
    formula_id: str
    formula_version: str
    name: str
    category: str
    status: str
    numbers: tuple[int, ...]
    public_reason: str
    reason_code: str | None


@dataclass(frozen=True)
class Generation:
    generation_id: str
    request_key: str
    status: str
    target_round: int
    based_on_round: int
    core_version: str
    generated_at: str | None
    games: tuple[PublicGame, ...]

    @classmethod
    def parse(cls, raw: Any, *, expected_key: str, expected_target: int,
              requested_ids: tuple[str, ...], expected_generation_id: str | None = None) -> "Generation":
        if not isinstance(raw, dict) or type(raw.get("contract_version")) is not int or raw["contract_version"] != CONTRACT_VERSION:
            raise ContractError("unsupported_contract")
        state = raw.get("status")
        gid = identifier(raw.get("generation_id"))
        key = identifier(raw.get("request_key"))
        target, based = positive(raw.get("target_round")), positive(raw.get("based_on_round"))
        if (key != expected_key or target != expected_target or target != based + 1
                or state not in _STATES or expected_generation_id is not None and gid != expected_generation_id):
            raise ContractError("generation_context_mismatch")
        values = raw.get("results", [])
        if not isinstance(values, list) or len(values) > 128:
            raise ContractError("invalid_results")
        games = []
        for item in values:
            if not isinstance(item, dict) or item.get("status") not in ("generated", "unavailable"):
                raise ContractError("invalid_result_state")
            ticket = numbers(item.get("numbers")) if item["status"] == "generated" else ()
            if item["status"] == "unavailable" and item.get("numbers") != []:
                raise ContractError("unavailable_has_numbers")
            reason_code = item.get("reason_code")
            games.append(PublicGame(identifier(item.get("formula_id")), identifier(item.get("formula_version")),
                                    text(item.get("name"), 180), text(item.get("category"), 180), item["status"],
                                    ticket, text(item.get("public_reason")),
                                    identifier(reason_code) if reason_code is not None else None))
        output_ids = tuple(g.formula_id for g in games)
        if len(set(output_ids)) != len(output_ids) or set(output_ids) - set(requested_ids):
            raise ContractError("unexpected_output")
        if state == "completed" and set(output_ids) != set(requested_ids):
            raise ContractError("missing_final_output")
        # Intermediate numbers are intentionally not returned as completed games.
        if state != "completed" and games:
            raise ContractError("uncommitted_output")
        generated_at = timestamp(raw.get("generated_at")) if state == "completed" else None
        return cls(gid, key, state, target, based, identifier(raw.get("core_version")), generated_at, tuple(games))
