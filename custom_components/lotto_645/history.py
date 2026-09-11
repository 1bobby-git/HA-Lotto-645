"""Shared Lotto history parsing and integrity validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import LottoDraw


class LottoHistoryError(ValueError):
    """Raised when a history mirror cannot be trusted."""


def _canonical_hash(rows: list[dict[str, Any]]) -> str:
    raw = json.dumps(
        rows,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def parse_history_payload(
    payload: Any,
    *,
    require_hash: bool = True,
) -> tuple[list[LottoDraw], dict[str, Any]]:
    """Validate a shared/bundled mirror and return contiguous draws + metadata."""
    if not isinstance(payload, dict):
        raise LottoHistoryError("로또 이력 데이터가 객체 형식이 아닙니다")
    rows = payload.get("draws")
    if not isinstance(rows, list) or not rows:
        raise LottoHistoryError("로또 이력 데이터가 비어 있습니다")

    try:
        draws = [LottoDraw.from_storage(item) for item in rows]
    except (KeyError, TypeError, ValueError) as err:
        raise LottoHistoryError(f"로또 이력 행이 유효하지 않습니다: {err}") from err

    draws.sort(key=lambda draw: draw.round)
    rounds = [draw.round for draw in draws]
    if rounds != list(range(1, draws[-1].round + 1)):
        raise LottoHistoryError("로또 이력은 1회부터 최신 회차까지 연속이어야 합니다")

    try:
        latest_round = int(payload.get("latest_round", draws[-1].round))
        draw_count = int(payload.get("draw_count", len(draws)))
    except (TypeError, ValueError) as err:
        raise LottoHistoryError("로또 이력 메타데이터가 유효하지 않습니다") from err
    if latest_round != draws[-1].round or draw_count != len(draws):
        raise LottoHistoryError("로또 이력 회차 메타데이터가 실제 데이터와 다릅니다")

    expected_hash = str(payload.get("draws_sha256", "") or "")
    if require_hash and not expected_hash:
        raise LottoHistoryError("로또 이력 무결성 해시가 없습니다")
    if expected_hash:
        actual_hash = _canonical_hash(rows)
        if actual_hash != expected_hash:
            raise LottoHistoryError("로또 이력 SHA-256 무결성 검증에 실패했습니다")

    metadata = {
        "schema_version": payload.get("schema_version"),
        "updated_at": payload.get("updated_at"),
        "latest_round": latest_round,
        "draw_count": draw_count,
        "draws_sha256": expected_hash or None,
        "source": payload.get("source"),
        "official_url": payload.get("official_url"),
        "community_source": payload.get("community_source"),
        "official_requests_this_update": payload.get("official_requests_this_update"),
    }
    return draws, metadata


def load_bundled_history() -> tuple[list[LottoDraw], dict[str, Any]]:
    """Load the release-bundled last-known-good history snapshot."""
    path = Path(__file__).with_name("history_seed.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise LottoHistoryError(f"번들 로또 이력을 읽을 수 없습니다: {err}") from err
    return parse_history_payload(payload, require_hash=True)
