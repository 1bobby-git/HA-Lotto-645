"""Migrate only actual stored pre-draw recommendations, not hindsight tickets."""
from __future__ import annotations
from datetime import datetime
from typing import Any

def record_evaluation(book, evaluation: Any, *, now: datetime | None = None) -> bool:
    """Recover real v1.8/1.9 stored tickets, never regenerate past predictions.

    Generation provenance must still precede the draw cutoff. An evaluation
    timestamp is NOT a generation timestamp. AI cannot inherit a local time.
    The authoritative draw is attached separately by the coordinator.
    """
    if not isinstance(evaluation, dict) or not isinstance(evaluation.get("results"), list):
        return False
    round_no = evaluation.get("round")
    changed = False
    for row in evaluation["results"]:
        if not isinstance(row, dict) or row.get("source") == "purchased":
            continue
        source = row.get("source", "analysis")
        stamp = row.get("generated_at")
        if stamp is None:
            stamp = evaluation.get("ai_generated_at") if source in ("ai", "ai_task") else evaluation.get("prediction_generated_at")
        based = row.get("based_on_round", evaluation.get("prediction_based_on_round"))
        snapshot = {"target_round": round_no, "based_on_round": based,
                    "local_generated_at": stamp, "ai_generated_at": stamp,
                    "recommendations": [{"method_id": row.get("method_id"),
                        "label": row.get("sensor_name", row.get("method_id")),
                        "source": source, "numbers": row.get("recommended_numbers")} ]}
        changed = book.record_snapshot(snapshot, now=now) or changed
    return changed

