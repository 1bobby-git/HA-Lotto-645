"""Opt-in, seeded sampler audit; not a forecast/backtest or RNG certification.

python scripts/validate_sampling.py --trials 1000000 --output report.json
No scipy/numpy dependency is installed in Home Assistant. Uses stdlib only.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
from itertools import combinations
import json
import math
from pathlib import Path
import random
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'custom_components/lotto_645/sampling.py'
spec = importlib.util.spec_from_file_location('lotto_sampling_audit', SOURCE)
sampling = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sampling)


def chi_square_44_sf(q):
    # Chi-square with even df=44: exact finite survival-series evaluation.
    x = q / 2
    return min(1., math.exp(-x) * sum(x ** k / math.factorial(k) for k in range(22)))


def holm(values):
    adjusted = [0.] * len(values)
    largest = 0.
    for rank, index in enumerate(sorted(range(len(values)), key=values.__getitem__)):
        largest = max(largest, min(1., (len(values) - rank) * values[index]))
        adjusted[index] = largest
    return adjusted


def audit(formula, trials, seed):
    rng = random.Random(seed)
    counts, pairs, hits = Counter(), Counter(), Counter()
    sums = sum_squares = products = 0
    first = previous = last = None
    started = perf_counter()
    sampler = sampling.SAMPLERS[formula]
    for _ in range(trials):
        ticket = sampler(sampling.NUMBERS, 6, rng)
        assert len(set(ticket)) == 6 and all(1 <= n <= 45 for n in ticket)
        counts.update(ticket)
        pairs.update(combinations(ticket, 2))
        hits[sum(n <= 6 for n in ticket)] += 1
        value = sum(ticket)
        if first is None:
            first = value
        if previous is not None:
            products += previous * value
        previous = last = value
        sums += value
        sum_squares += value * value
    mean = sums / trials
    variance = sum_squares / trials - mean * mean
    expected = trials * 6 / 45
    # Count covariance has eigenvalue M*p*(1-p)*45/44 on the sum-zero subspace.
    eigenvalue = trials * (6 / 45) * (39 / 45) * 45 / 44
    q = sum((counts[n] - expected) ** 2 for n in sampling.NUMBERS) / eigenvalue
    pair_expected = trials / 66
    lag_cov = products / (trials-1) - ((sums-last)/(trials-1))*((sums-first)/(trials-1))
    return {
        'formula_id': formula, 'trials': trials, 'seed': seed, 'rng': 'random.Random (test only)',
        'source_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        'seconds': round(perf_counter() - started, 3), 'valid_tickets': trials,
        'counts': dict(sorted(counts.items())), 'hit_counts': {str(k): hits[k] for k in range(7)},
        'mean_sum': mean, 'sd_sum': math.sqrt(variance), 'sum_lag1_correlation': lag_cov / variance,
        'pair_count_min': min(pairs.values()), 'pair_count_max': max(pairs.values()),
        'pair_expected': pair_expected, 'covariance_adjusted_chi_square_44': q,
        'p_value_asymptotic': chi_square_44_sf(q),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trials', type=int, default=100000)
    parser.add_argument('--seed', type=int, default=20260914)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.trials < 100:
        parser.error('At least 100 trials required')
    results = []
    for i, formula in enumerate(sampling.UNIFORM_IDS):
        result = audit(formula, args.trials, args.seed + i)
        results.append(result)
        print(formula, 'p=', result['p_value_asymptotic'], 'mean=', result['mean_sum'], flush=True)
    for result, adjusted in zip(results, holm([r['p_value_asymptotic'] for r in results])):
        result['p_value_holm'] = adjusted
        result['reject_uniform_marginals_at_0_01'] = adjusted < .01
    payload = {
        'created_at': datetime.now(timezone.utc).isoformat(), 'component_version': '1.12.0',
        'scope': 'Six sampler cores, no historical exclusions/fixed numbers; no winning prediction claim',
        'limitations': 'Asymptotic covariance-adjusted marginal test; not Monte Carlo calibrated. '
                       'Pair, hit and serial summaries are descriptive, not independent hypothesis tests. '
                       'Small-space exhaustive tests establish combinatorial correctness separately. '
                       'These simulations do not certify the OS entropy source or real lottery draws.',
        'theory': {'combinations': math.comb(45,6), 'mean_sum': 138, 'variance_sum': 897,
                   'expected_hits': .8, 'hit_probabilities': [math.comb(6,k)*math.comb(39,6-k)/math.comb(45,6) for k in range(7)]},
        'results': results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
