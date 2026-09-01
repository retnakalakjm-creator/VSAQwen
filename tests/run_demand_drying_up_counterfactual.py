from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from background.qualification import PatternQualification
from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import EvidenceCode
from scanner import ScannerEngine
from tests.conditional_demand_drying_up_counterfactual import apply_counterfactual
from tests.decision_outcome_labeling import label_outcome
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS
from trend import TrendAnalyzer


def _direction(candidate) -> int | None:
    if candidate.qualification is PatternQualification.PERSISTENT_BULLISH:
        return 1
    if candidate.qualification is PatternQualification.PERSISTENT_BEARISH:
        return -1
    return None


def _audit_symbol(symbol: str, sample_bars: int, horizons: tuple[int, ...], refresh: bool) -> list[dict[str, object]]:
    daily = download_data(symbol, refresh=refresh)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    scanner = ScannerEngine()
    sample_start = max(scanner.MIN_REPLAY_BARS, len(metrics) - sample_bars - max(horizons))
    history = []
    rows: list[dict[str, object]] = []

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        evidence = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=list(trend.structure.structural_swings),
        )
        history.append(evidence)
        if index < sample_start or index + max(horizons) >= len(metrics):
            continue

        candidate = scanner.evaluate(
            trend=trend,
            evidence=evidence,
            history=history,
            bar_index=index,
            week=scanner._week_at(metrics, index),
        )
        if not candidate.actionable or EvidenceCode.DEMAND_DRYING_UP not in {
            item.code for item in candidate.scoring_evidence
        }:
            continue

        counterfactual = apply_counterfactual(trend, candidate)
        if not counterfactual.suppressed:
            continue

        direction = _direction(candidate)
        if direction is None:
            continue

        for horizon in horizons:
            outcome = label_outcome(metrics, signal_index=index, direction=direction, horizon=horizon)
            if outcome.forward_return is None:
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "state": counterfactual.state,
                    "direction": counterfactual.direction,
                    "horizon": horizon,
                    "forward_return": outcome.forward_return,
                    "mfe": outcome.maximum_favorable_excursion,
                    "mae": outcome.maximum_adverse_excursion,
                }
            )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit-only counterfactual suppression for DEMAND_DRYING_UP target contexts.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    horizons = (3, 5, 10)

    all_rows: list[dict[str, object]] = []
    skipped: list[tuple[str, str, str]] = []
    for symbol in SYMBOLS:
        try:
            all_rows.extend(_audit_symbol(symbol, args.sample_bars, horizons, args.refresh))
        except Exception as exc:
            skipped.append((symbol, type(exc).__name__, str(exc)))

    print("=== DEMAND_DRYING_UP CONDITIONAL COUNTERFACTUAL AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols with suppressed candidates: {len({row['symbol'] for row in all_rows})}")
    print(f"suppressed candidate-horizon rows: {len(all_rows)}")
    print()
    print(f"{'State':<12}{'Direction':<10}{'H':>4}{'Cases':>8}{'MeanRet':>12}{'Positive':>10}{'MeanMFE':>11}{'MeanMAE':>11}")

    groups: dict[tuple[str, str, int], list[dict[str, object]]] = {}
    for row in all_rows:
        key = (str(row["state"]), str(row["direction"]), int(row["horizon"]))
        groups.setdefault(key, []).append(row)

    for (state, direction, horizon), rows in sorted(groups.items()):
        returns = [float(row["forward_return"]) for row in rows]
        mfes = [float(row["mfe"]) for row in rows if row["mfe"] is not None]
        maes = [float(row["mae"]) for row in rows if row["mae"] is not None]
        print(
            f"{state:<12}{direction:<10}{horizon:>4}{len(returns):>8}"
            f"{sum(returns)/len(returns):>11.3%}"
            f"{sum(value > 0 for value in returns):>6}/{len(returns):<4}"
            f"{sum(mfes)/len(mfes):>10.3%}"
            f"{sum(maes)/len(maes):>10.3%}"
        )

    print()
    print("=== SUPPRESSED CASES BY SYMBOL ===")
    symbol_counts: dict[str, int] = {}
    for row in all_rows:
        symbol = str(row["symbol"])
        symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
    for symbol in SYMBOLS:
        if symbol in symbol_counts:
            print(f"{symbol:<14}{symbol_counts[symbol]:>6}")

    if skipped:
        print()
        print("=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
