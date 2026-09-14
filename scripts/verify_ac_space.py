"""Independent full-space AC count, not a prediction backtest.

Run: python scripts/verify_ac_space.py --output /tmp/ac-space.json
This deliberately does not import the production implementation/constants.
"""
from __future__ import annotations

import argparse
from itertools import combinations
import json
from math import comb
from pathlib import Path


def enumerate_space(maximum: int = 45) -> dict:
    if type(maximum) is not int or not 6 <= maximum <= 45:
        raise ValueError("maximum must be an integer from 6 to 45")
    histogram = [0] * 11
    for row in combinations(range(1, maximum + 1), 6):
        # Reference uses a bitset rather than production's difference set.
        mask = 0
        for left, right in combinations(row, 2):
            mask |= 1 << (right - left)
        histogram[mask.bit_count() - 5] += 1
    assert sum(histogram) == comb(maximum, 6)
    return {
        "scope": "all_combinations_not_historical_draws",
        "maximum": maximum,
        "total_combinations": sum(histogram),
        "ac_histogram": {str(i): n for i, n in enumerate(histogram)},
        "ac_minimum": 7,
        "ac_ge_7_count": sum(histogram[7:]),
        "ac_ge_7_ratio": sum(histogram[7:]) / sum(histogram),
        "predictive_evidence": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--maximum", type=int, default=45)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    text = json.dumps(enumerate_space(args.maximum), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
