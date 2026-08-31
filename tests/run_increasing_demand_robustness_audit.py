from __future__ import annotations

import argparse
from collections import defaultdict
import random
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from matched_increasing_demand_audit import _scan_cases, build_matches
from run_nse_increasing_demand_universe_audit import SYMBOLS


def _unique_pairs(pairs):
    used = set()
    result = []
    for pair in sorted(
        pairs,
        key=lambda p: (
            p.target.horizon,
            p.target.symbol,
            p.score_gap,
            p.pressure_gap,
            p.age_gap,
            abs(p.target.bar_index - p.control.bar_index),
        ),
    ):
        key = (pair.control.symbol, pair.control.bar_index, pair.horizon)
        if key in used:
            continue
        used.add(key)
        result.append(pair)
    return result


def _bootstrap_delta(pairs, iterations: int, seed: int):
    deltas = [
        pair.target.forward_return - pair.control.forward_return
        for pair in pairs
        if pair.target.forward_return is not None
        and pair.control.forward_return is not None
    ]
    if not deltas:
        return None
    rng = random.Random(seed)
    observed = sum(deltas) / len(deltas)
    samples = []
    for _ in range(iterations):
        sample = [deltas[rng.randrange(len(deltas))] for _ in deltas]
        samples.append(sum(sample) / len(sample))
    samples.sort()
    low = samples[max(0, int(iterations * 0.025) - 1)]
    high = samples[min(iterations - 1, int(iterations * 0.975))]
    negative = sum(delta < 0 for delta in deltas)
    return observed, low, high, negative


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap robustness audit for increasing_demand matched controls.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--score-band", type=float, default=0.10)
    parser.add_argument("--pressure-band", type=float, default=0.25)
    parser.add_argument("--max-age-gap", type=int, default=1)
    parser.add_argument("--iterations", type=int, default=5000)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    horizons = (3, 5, 10)

    all_cases = []
    skipped = []
    for symbol in SYMBOLS:
        try:
            all_cases.extend(_scan_cases(symbol, args.sample_bars, horizons, args.refresh))
        except Exception as exc:
            skipped.append((symbol, type(exc).__name__, str(exc)))

    pairs = build_matches(
        all_cases,
        score_band=args.score_band,
        pressure_band=args.pressure_band,
        max_age_gap=args.max_age_gap,
    )
    pairs = _unique_pairs(pairs)

    print("=== INCREASING_DEMAND ROBUSTNESS AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols scanned: {len({c.symbol for c, _ in all_cases})}")
    print(f"unique matched pairs: {len(pairs)}")
    print(f"bootstrap iterations: {args.iterations}")
    print()
    print(f"{'Change':<14}{'Horizon':>8}{'Pairs':>8}{'Delta':>12}{'95% Low':>12}{'95% High':>12}{'Negative':>10}")

    grouped = defaultdict(list)
    for pair in pairs:
        grouped[(pair.target.change, pair.horizon)].append(pair)

    for key in sorted(grouped):
        change, horizon = key
        bucket = grouped[key]
        result = _bootstrap_delta(bucket, args.iterations, seed=42 + horizon)
        if result is None:
            continue
        observed, low, high, negative = result
        print(
            f"{change:<14}{horizon:>8}{len(bucket):>8}"
            f"{observed:>11.3%}{low:>11.3%}{high:>11.3%}"
            f"{negative:>6}/{len(bucket):<4}"
        )

    print()
    print("95% Low/High are percentile bootstrap intervals for the paired target-control return delta.")
    print("A wholly negative interval supports robust target underperformance for that bucket.")

    if skipped:
        print()
        print("=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
