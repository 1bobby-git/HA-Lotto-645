#!/usr/bin/env python3
"""Offline rolling-origin smoke audit of all 16 methods against bundled draws.

This is a retrospective diagnostic, not preregistered evidence of predictivity.
The only Saju profile is a fixed synthetic test fixture, not the owner's data.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
import hashlib
import importlib
import json
import math
from pathlib import Path
import sys
import time
import types

ROOT = Path(__file__).resolve().parents[1]
for name, path in (("custom_components", ROOT / "custom_components"),
                   ("custom_components.lotto_645", ROOT / "custom_components/lotto_645")):
    module = types.ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules.setdefault(name, module)
engine = importlib.import_module("custom_components.lotto_645.analysis")
methods = importlib.import_module("custom_components.lotto_645.methods")
history_module = importlib.import_module("custom_components.lotto_645.history")
PROFILE = {"calendar":"solar", "birth_date":"1990-05-17", "birth_time":"14:30",
           "lunar_leap_month":False, "gender":"male", "birth_place":"Synthetic fixture",
           "timezone":"Asia/Seoul", "true_solar_time":False, "longitude":None}
IDS = tuple(method.method_id for method in methods.METHODS)


def evaluate(target_index: int) -> dict:
    history, _ = history_module.load_bundled_history()
    training, target = history[:target_index], history[target_index]
    started = time.perf_counter()
    result = engine.build_analysis(training, IDS, 0, PROFILE)
    assert result.based_on_round < target.round and result.target_round == target.round
    assert len(result.recommendations) == len(IDS)
    assert len({r.numbers for r in result.recommendations}) == len(IDS)
    past = {row.numbers for row in training}
    games = []
    for r in result.recommendations:
        assert len(set(r.numbers)) == 6 and all(type(n) is int and 1 <= n <= 45 for n in r.numbers)
        assert r.numbers not in past and math.isfinite(r.score) and 0 <= r.score <= 1
        games.append({"method_id":r.method_id, "numbers":r.numbers,
                      "matches":len(set(r.numbers) & set(target.numbers)), "score":r.score})
    return {"training_through":training[-1].round, "target_round":target.round,
            "target_numbers":target.numbers, "games":games,
            "elapsed_seconds":round(time.perf_counter()-started,3)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--rounds',type=int,default=12)
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--output',type=Path,default=ROOT/'docs/validation-v1.6.0.json')
    args = parser.parse_args()
    history, _ = history_module.load_bundled_history()
    if not 1 <= args.rounds <= len(history)-30:
        raise SystemExit('rounds must leave at least 30 earlier draws')
    indices = list(range(len(history)-args.rounds,len(history)))
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        rows = list(pool.map(evaluate, indices))
    summary = []
    for method_id in IDS:
        counts = [next(g['matches'] for g in row['games'] if g['method_id']==method_id) for row in rows]
        summary.append({"method_id":method_id,"games":len(counts),"total_matches":sum(counts),
                        "mean_matches":sum(counts)/len(counts),"maximum_matches":max(counts),
                        "random_baseline_mean":.8})
    report = {"version":"1.6.0", "created_at":datetime.now(UTC).isoformat(),
        "history_sha256":hashlib.sha256((ROOT/'custom_components/lotto_645/history_seed.json').read_bytes()).hexdigest(),
        "history_through":history[-1].round, "method_order":IDS,
        "algorithm_sha256":{name:hashlib.sha256((ROOT/'custom_components/lotto_645'/name).read_bytes()).hexdigest()
                            for name in ('analysis.py','methods.py','myungri.py','saju_rules.py')},
        "synthetic_profile":PROFILE, "generation_nonce":0,
        "checks": {"all_16_methods":True,"no_future_draw_as_input":True,
            "six_distinct_in_range":True,"no_exact_past_winner":True,
            "no_duplicate_portfolio_games":True,"finite_normalized_scores":True},
        "interpretation": "회고적 소표본 동작 점검. 동일 회차의 게임은 상관되며 출생정보는 합성 테스트값이다. 당첨 예측력·명리학 타당성·방법 우열을 입증하지 않는다.",
        "predictive_validity_established":False, "wall_seconds":round(time.perf_counter()-started,3),
        "summaries":summary,"rounds":rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({"rounds":len(rows),"games":len(rows)*len(IDS),"all_checks_passed":True,
                      "wall_seconds":report['wall_seconds']},ensure_ascii=False))


if __name__=='__main__':
    main()
