#!/usr/bin/env python3
"""Reproducible exploratory rolling-origin check; not a predictive certification.

No official-site calls, no AI calls and no real user's birth information.
Every test draw t is withheld from the input (only 1..t-1 is given to the engine).
Run: python scripts/audit_formulas.py --rounds 26 --workers 4
"""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import sys
import types

ROOT=Path(__file__).resolve().parents[1]
for name,path in [('custom_components',ROOT/'custom_components'),('custom_components.lotto_645',ROOT/'custom_components/lotto_645')]:
    module=types.ModuleType(name);module.__path__=[str(path)];sys.modules.setdefault(name,module)
analysis=importlib.import_module('custom_components.lotto_645.analysis')
methods=importlib.import_module('custom_components.lotto_645.methods')
history_module=importlib.import_module('custom_components.lotto_645.history')

# Artificial fixed fixture, NOT account owner/user information.
FIXTURE={'calendar':'solar','birth_date':'1990-05-17','birth_time':'14:30',
         'gender':'male','birth_place':'SYNTHETIC TEST FIXTURE', 'timezone':'Asia/Seoul',
         'true_solar_time':False,'lunar_standard':'korean'}


def evaluate(target_index):
    history,_=history_module.load_bundled_history()
    result=analysis.build_analysis(history[:target_index],tuple(m.method_id for m in methods.METHODS),0,FIXTURE)
    truth=history[target_index]
    assert result.target_round==truth.round
    assert len({r.numbers for r in result.recommendations})==len(methods.METHODS)
    rows=[]
    for rec in result.recommendations:
        assert 0<=rec.score<=1
        assert rec.numbers not in {r.numbers for r in history[:target_index]}
        rows.append({'round':truth.round,'method_id':rec.method_id,'numbers':' '.join(map(str,rec.numbers)),
                     'winning_numbers':' '.join(map(str,truth.numbers)),
                     'matches':len(set(rec.numbers)&set(truth.numbers)), 'score':round(rec.score,6)})
    return rows


def null_distribution(rounds):
    dist=[1.0]
    masses=[analysis.match_probability(k) for k in range(7)]
    for _ in range(rounds):
        new=[0.]*(len(dist)+6)
        for i,p in enumerate(dist):
            for k,q in enumerate(masses):new[i+k]+=p*q
        dist=new
    return dist


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rounds',type=int,default=26);ap.add_argument('--workers',type=int,default=4)
    args=ap.parse_args();history,meta=history_module.load_bundled_history()
    if not 1<=args.rounds<=len(history)-30:raise ValueError('Invalid number of held-out draws')
    indices=range(len(history)-args.rounds,len(history)); rows=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for batch in pool.map(evaluate,indices):
            rows.extend(batch);print(f"tested withheld draw {batch[0]['round']}",flush=True)
    dist=null_distribution(args.rounds); report=[]
    for method in methods.METHODS:
        selected=[r for r in rows if r['method_id']==method.method_id]
        total=sum(r['matches'] for r in selected);p=sum(dist[total:])
        report.append({'method_id':method.method_id,'name':method.label,'games':len(selected),
                       'total_matches':total,'mean_matches':round(total/len(selected),6),
                       'games_with_at_least_3_matches':sum(r['matches']>=3 for r in selected),
                       'maximum_matches':max(r['matches'] for r in selected),
                       'upper_tail_p':round(p,6),'bonferroni_p_16_methods':round(min(1,16*p),6)})
    raw_source=(ROOT/'custom_components/lotto_645/history_seed.json').read_bytes()
    result={'scope':'exploratory historical replay; NOT prospective or independent model validation',
            'test_rounds':[history[i].round for i in indices], 'training':'expanding 1..t-1 only; nonce 0; all 16 methods together',
            'saju_profile':'synthetic fixture in scripts/audit_formulas.py, not the account owner',
            'history_sha256':hashlib.sha256(raw_source).hexdigest(), 'draws_sha256':meta['draws_sha256'],
            'expected_matches_per_game':.8, 'first_prize_odds':'1/8,145,060',
            'statistical_test':'one-sided exact convolution of Hypergeom(45,6,6) over draws; Bonferroni across16methods',
            'limitations':['Historical outcomes were available during development; this is not a preregistered holdout.',
                           'Small sample; cannot certify superiority or infer a reliable winning probability.',
                           'Choosing the best result after this replay is multiple testing, not validated prediction.'],
            'results':report}
    out=ROOT/'docs';out.mkdir(exist_ok=True)
    (out/'formula-audit-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with (out/'formula-audit-predictions.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    print(json.dumps(report,ensure_ascii=False),flush=True)

if __name__=='__main__': main()
