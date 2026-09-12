"""Strict, offline Lotto 6/45 QR decoding. Never follow a ticket URL.

The four-digit draw and q/m/s + 12-digit game records are public QR payload
conventions, not purchase/ownership authentication. Only explicit save stores
parsed numbers. The receipt suffix is discarded and must not enter logs.
"""
from __future__ import annotations

import re
from urllib.parse import parse_qs, urlsplit

from .purchased_tickets import PurchaseInputError, SLOTS, parse_ticket

_ALLOWED = {
    "m.dhlottery.co.kr": {"/qr.do"},
    "www.dhlottery.co.kr": {"/qr.do"},
    "dhlottery.co.kr": {"/qr.do"},
    "qr.645lotto.net": {"/", ""},
}
_PAYLOAD = re.compile(r"(?P<round>[0-9]{4})(?P<games>(?:[qms][0-9]{12}){1,5})(?P<receipt>[0-9]{10})?", re.ASCII)


def parse_ticket_qr(value: str) -> dict:
    """Return only a round and up to five canonical games; reject ambiguity."""
    def fail() -> None:
        raise PurchaseInputError("qr", "invalid_ticket_qr")

    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 2048:
        fail()
    try:
        parsed = urlsplit(value.strip())
        if (parsed.scheme not in ("https", "http") or parsed.hostname not in _ALLOWED
                or parsed.path not in _ALLOWED[parsed.hostname]
                or parsed.username or parsed.password or parsed.fragment
                or parsed.port not in (None, 80 if parsed.scheme == "http" else 443)):
            fail()
        query = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=True, max_num_fields=5)
        if set(query) - {"v", "method"} or len(query.get("v", [])) != 1:
            fail()
        if "method" in query and query["method"] != ["winQr"]:
            fail()
        match = _PAYLOAD.fullmatch(query["v"][0])
        if match is None or int(match["round"]) < 1:
            fail()
        games = re.findall(r"[qms]([0-9]{12})", match["games"])
        values = {f"game_{slot.lower()}": ", ".join(map(str, parse_ticket(numbers)))
                  for slot, numbers in zip(SLOTS, games)}
        return {"round": int(match["round"]), "values": values,
                "game_count": len(values), "purchase_verified": False}
    except (ValueError, TypeError, KeyError) as err:
        raise PurchaseInputError("qr", "invalid_ticket_qr") from err
