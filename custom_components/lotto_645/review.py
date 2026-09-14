"""Local pre-draw recommendation reviews, not a future winning probability.

Exactly one (latest eligible) ticket per method per draw. Results/corrections are
upserts, never another vote. Exact matches are removed before one-to-one ±1
matching. Near matches have NO effect on the official prize classification.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from functools import lru_cache
from statistics import fmean
from typing import Any

from .models import LottoDraw
from .published_results import draw_cutoff
from .purchased_tickets import parse_ticket
from .result_evaluator import evaluate_ticket

POLICY = "local_review_v1_exact80_near15_distance5"
NOTICE = "사용자의 추첨 전 저장번호를 사후 비교한 리뷰입니다. ±1은 당첨이 아니며 별점·점수는 미래 당첨확률이나 검증된 예측력이 아닙니다."


def compare_numbers(numbers: list[int] | tuple[int, ...], draw: LottoDraw) -> dict[str, Any]:
    """Maximize distinct near pairs AFTER preserving all exact matches."""
    ticket = parse_ticket(numbers)
    actual = parse_ticket(draw.numbers)
    prize = evaluate_ticket(ticket, draw)
    exact = set(ticket) & set(actual)
    left = tuple(n for n in ticket if n not in exact)
    right = tuple(n for n in actual if n not in exact)

    @lru_cache(maxsize=None)
    def pair(i: int, used: int) -> tuple[tuple[int, int], ...]:
        if i == len(left):
            return ()
        options = [pair(i + 1, used)]
        for j, value in enumerate(right):
            if not used & (1 << j) and abs(left[i] - value) == 1:
                options.append(((left[i], value),) + pair(i + 1, used | (1 << j)))
        return min(options, key=lambda p: (-len(p), p))

    nearby = pair(0, 0)
    # Sorted matching minimizes total absolute distance on a number line.
    distance_pairs = list(zip(ticket, actual, strict=True))
    distance = sum(abs(a - b) for a, b in distance_pairs)
    # Max distance between two distinct-six subsets of 1..45 is 234.
    closeness = 1 - min(distance, 234) / 234
    components = {"exact": 80 * len(exact) / 6,
                  "near_one_to_one": 15 * (len(exact) + len(nearby)) / 6,
                  "distance": 5 * closeness}
    score = round(sum(components.values()), 4)
    return {
        "numbers": list(ticket), "winning_numbers": list(actual), "bonus_number": draw.bonus,
        **prize, "exact_match_count": len(exact), "near_match_count": len(nearby),
        "near_pairs": [{"recommended": a, "drawn": b, "delta": b - a} for a, b in nearby],
        "distance_pairs": [{"recommended": a, "drawn": b, "distance": abs(a-b)} for a,b in distance_pairs],
        "total_absolute_distance": distance,
        "score_components": {k: round(v, 6) for k, v in components.items()},
        "review_score": score, "stars": round(score / 20, 2), "score_policy": POLICY,
        "review_notice": NOTICE,
    }


def _cutoff(round_no: int) -> datetime:
    try:
        return draw_cutoff(round_no)
    except (OverflowError, ValueError) as err:
        raise ValueError("Unsupported review round date") from err


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("Missing review timestamp")
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("Naive review timestamp")
    return result


class ReviewBook:
    """Small, persistent per-round ledger; no invented retrospective tickets."""

    def __init__(self) -> None:
        self.rounds: dict[str, dict] = {}

    @classmethod
    def from_storage(cls, payload: Any) -> 'ReviewBook':
        book = cls()
        if payload is None:
            return book
        if (not isinstance(payload, dict) or payload.get("version") != 1
                or not isinstance(payload.get("rounds"), dict)):
            raise ValueError("Invalid review storage; must not overwrite")
        for key, raw in payload["rounds"].items():
            if not isinstance(key, str) or not key.isascii() or not key.isdigit() or not 1 <= int(key) <= 999999:
                raise ValueError("Invalid reviewed round")
            if str(int(key)) != key or not isinstance(raw, dict) or not isinstance(raw.get("predictions"), dict):
                raise ValueError("Invalid reviewed predictions")
            row = {"predictions": {}, "result": None}
            for method_id, prediction in raw["predictions"].items():
                if not isinstance(method_id, str) or not 1 <= len(method_id) <= 100 or not isinstance(prediction, dict):
                    raise ValueError("Invalid review method")
                if prediction.get("source") == "purchased":
                    raise ValueError("Purchases cannot be method reviews")
                when = _timestamp(prediction.get("generated_at"))
                based_on = prediction.get("based_on_round")
                if type(based_on) is not int or not 0 < based_on < int(key) or when >= _cutoff(int(key)):
                    raise ValueError("Not a pre-draw prediction")
                row["predictions"][method_id] = {
                    "numbers": list(parse_ticket(prediction.get("numbers"))),
                    "label": str(prediction.get("label", method_id))[:180],
                    "generated_at": when.isoformat(), "based_on_round": based_on,
                    "source": str(prediction.get("source", "analysis"))[:40],
                }
            book.rounds[key] = row
            result = raw.get("result")
            if result is not None:
                if not isinstance(result, dict) or not isinstance(result.get("draw"), dict):
                    raise ValueError("Invalid review result object")
                draw_raw = result["draw"]
                numbers = parse_ticket(draw_raw.get("numbers"))
                bonus = draw_raw.get("bonus")
                if (type(draw_raw.get("round")) is not int or draw_raw["round"] != int(key)
                        or type(bonus) is not int or not 1 <= bonus <= 45 or bonus in numbers
                        or type(result.get("confirmed")) is not bool):
                    raise ValueError("Invalid review result")
                draw = LottoDraw(int(key), str(draw_raw.get("draw_date", "")), numbers, bonus)
                book.set_result(draw, confirmed=result["confirmed"], status=str(result.get("status", "")))
        return book

    def to_storage(self) -> dict:
        return {"version": 1, "rounds": deepcopy(self.rounds)}

    def record_snapshot(self, snapshot: Any, *, now: datetime | None = None) -> bool:
        """Import real persisted snapshots; freeze each method at the cutoff."""
        if not isinstance(snapshot, dict):
            return False
        r, based = snapshot.get("target_round"), snapshot.get("based_on_round")
        if (type(r) is not int or not 1 <= r <= 999999 or type(based) is not int
                or not 0 < based < r or not isinstance(snapshot.get("recommendations"), list)):
            return False
        now = now or datetime.now(UTC)
        try:
            cutoff = _cutoff(r)
        except ValueError:
            return False
        accepted = {}
        for raw in snapshot["recommendations"]:
            if not isinstance(raw, dict) or raw.get("source") == "purchased":
                continue
            method_id = raw.get("method_id")
            if not isinstance(method_id, str) or not 1 <= len(method_id) <= 100:
                continue
            timestamp_key = "ai_generated_at" if raw.get("source") in ("ai", "ai_task") else "local_generated_at"
            try:
                when = _timestamp(raw.get("generated_at", snapshot.get(timestamp_key)))
                numbers = parse_ticket(raw.get("numbers"))
                if when >= cutoff or when > now:
                    continue
            except (TypeError, ValueError, KeyError):
                continue
            accepted[method_id] = {"numbers": list(numbers), "label": str(raw.get("label", method_id))[:180],
                                   "generated_at": when.isoformat(), "based_on_round": based,
                                   "source": str(raw.get("source", "analysis"))[:40]}
        if not accepted:
            return False
        row = self.rounds.setdefault(str(r), {"predictions": {}, "result": None})
        changed = False
        for method_id, prediction in accepted.items():
            old = row["predictions"].get(method_id)
            if old is not None and (now >= cutoff or _timestamp(prediction["generated_at"]) <= _timestamp(old["generated_at"])):
                continue
            if prediction != old:
                row["predictions"][method_id] = prediction
                changed = True
        return changed

    def set_result(self, draw: LottoDraw, *, confirmed: bool, status: str) -> bool:
        numbers = parse_ticket(draw.numbers)
        if (type(confirmed) is not bool or type(draw.bonus) is not int
                or not 1 <= draw.bonus <= 45 or draw.bonus in numbers):
            raise ValueError("Invalid review result")
        row = self.rounds.get(str(draw.round))
        if not row:
            return False
        old = row.get("result")
        if old and old["confirmed"] and not confirmed:
            return False  # official history always outranks an overlay
        result = {"draw": {"round": draw.round, "draw_date": draw.draw_date,
                           "numbers": list(draw.numbers), "bonus": draw.bonus},
                  "confirmed": confirmed, "status": status}
        if result == old:
            return False
        row["result"] = result
        return True

    def invalidate_provisional(self, round_no: int) -> bool:
        row = self.rounds.get(str(round_no), {})
        if row.get("result") and not row["result"]["confirmed"]:
            row["result"] = None
            return True
        return False

    def round_review(self, round_no: int) -> dict:
        row = self.rounds.get(str(round_no), {})
        result = row.get("result")
        if not result:
            return {"round": round_no, "status": "waiting", "methods": [], "notice": NOTICE}
        d = result["draw"]
        draw = LottoDraw(d["round"], d["draw_date"], tuple(d["numbers"]), d["bonus"])
        methods = [{"method_id": key, **prediction, **compare_numbers(prediction["numbers"], draw)}
                   for key, prediction in row["predictions"].items()]
        for method in methods:
            # Competition ranks: ties share a rank, no arbitrary numerical preference.
            method["rank_this_round"] = 1 + sum(m["review_score"] > method["review_score"] for m in methods)
        return {"round": round_no, "status": "confirmed" if result["confirmed"] else "provisional",
                "methods": sorted(methods, key=lambda m: (-m["review_score"], m["method_id"])),
                "peer_count": len(methods), "notice": NOTICE, "policy": POLICY}

    def summary(self, method_id: str, reports: dict[int, dict] | None = None) -> dict:
        rows = []
        provisional = None
        for key in sorted(self.rounds, key=int):
            row = self.rounds[key]
            if method_id not in row["predictions"] or not row.get("result"):
                continue
            report = reports[int(key)] if reports is not None else self.round_review(int(key))
            item = next(m for m in report["methods"] if m["method_id"] == method_id)
            item = {"round": int(key), **item}
            if report["status"] == "confirmed":
                rows.append(item)
            else:
                provisional = item
        scores = [r["review_score"] for r in rows]
        mean = round(fmean(scores), 4) if scores else None
        return {"reviewed_rounds": len(rows), "mean_score": mean,
                "stars": round(mean / 20, 2) if mean is not None else None,
                "total_score": round(sum(scores), 4),
                "first_review_round": rows[0]["round"] if rows else None,
                "last_review_round": rows[-1]["round"] if rows else None,
                "latest_confirmed": rows[-1] if rows else None, "latest_provisional": provisional,
                "winning_rounds": sum(r["prize_rank"] is not None for r in rows),
                "exact_matches_total": sum(r["exact_match_count"] for r in rows),
                "near_matches_total": sum(r["near_match_count"] for r in rows),
                "highest_prize_rank": min((r["prize_rank"] for r in rows if r["prize_rank"] is not None), default=None),
                "history_preview": [{k: r[k] for k in ("round", "review_score", "stars", "exact_match_count", "near_match_count", "prize")} for r in rows[-12:]],
                "policy": POLICY, "notice": NOTICE}


def review_name(label: str, summary: dict | None) -> str:
    summary = summary or {}
    if summary.get("mean_score") is not None:
        return f"★{summary['stars']:.1f} · {summary['mean_score']:.1f}점 | {label}"
    p = summary.get("latest_provisional")
    if p:
        return f"★{p['stars']:.1f} · {p['review_score']:.1f}점(잠정) | {label}"
    return f"☆평가대기 | {label}"
