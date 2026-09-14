"""Persist sampled tickets, never reconstruct random pre-draw recommendations."""
from __future__ import annotations

from hashlib import sha256
import json

from .methods import METHODS_BY_ID
from .sampling import FORMULA_VERSION, validate_sampled_ticket


def cache_key(history, method_ids, nonce):
    payload = [(d.round, d.numbers, d.bonus) for d in history]
    return {"version": FORMULA_VERSION, "based_on_round": history[-1].round,
            "methods": list(method_ids), "nonce": nonce,
            "history_digest": sha256(json.dumps(payload).encode()).hexdigest()}


def restore_tickets(cache, history, method_ids, nonce):
    if not isinstance(cache, dict) or cache.get("key") != cache_key(history, method_ids, nonce):
        return {}
    expected = {key for key in method_ids if METHODS_BY_ID[key].sampling}
    raw = cache.get("tickets")
    if not isinstance(raw, dict) or set(raw) != expected:
        return {}
    try:
        tickets = {
            key: validate_sampled_ticket(METHODS_BY_ID[key].sampling, values)
            for key, values in raw.items()
        }
        if any(len(t) != 6 for t in tickets.values()) or len(set(tickets.values())) != len(tickets):
            return {}
        if set(tickets.values()) & {d.numbers for d in history}:
            return {}
    except (ValueError, TypeError, KeyError):
        return {}
    return tickets


def store_tickets(analysis, history, method_ids, nonce):
    return {"key": cache_key(history, method_ids, nonce),
            "tickets": {r.method_id: list(r.numbers) for r in analysis.recommendations
                        if METHODS_BY_ID[r.method_id].sampling}}
