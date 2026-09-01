from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from model.evidence_result_model import EvidenceResult
from models import ClosePosition, Direction, Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection, VolumeClass
from scanner import ScannerEngine
from trend import TrendAnalyzer
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS

HORIZONS = (3, 5, 10)
PROMOTED_CONTEXTS = {("healthy", "up"), ("unknown", "range")}
WEIGHTS = (0.10, 0.15, 0.20, 0.25, 0.30)


def _is_hidden_demand(row) -> bool:
    return (
        Direction(int(row["direction"])) == Direction.DOWN
        and VolumeClass(int(row["volume_class"])) >= VolumeClass.HIGH
        and ClosePosition(int(row["close_position"])) >= ClosePosition.UPPER
    )


def _synthetic_hidden_demand(metrics, index: int) -> Evidence:
    week = metrics.iloc[index].get("week_beginning")
    return Evidence(
        code=EvidenceCode.HIDDEN_DEMAND,
        category=EvidenceCategory.DEMAND,
        direction=EvidenceDirection.BULLISH,
        strength=1.0,
        weight=1.0,
        observation="Synthetic HIDDEN_DEMAND for counterfactual decision audit.",
        description="Counterfactual HIDDEN_DEMAND event; production collector is unchanged.",
        bar_index=index,
        week_beginning=str(week),
    )


def _future_return(metrics, index: int, horizon: int) -> float | None:
    if index + horizon >= len(metrics):
        return None
    current = float(metrics.iloc[index]["close"])
    future = float(metrics.iloc[index + horizon]["close"])
    if current <= 0.0:
        return None
    return future / current - 1.0


def _evaluate(scanner, trend, evidence, history, metrics, index: int, weight: float):
    baseline = scanner.evaluate(
        trend=trend,
        evidence=evidence,
        history=history,
        bar_index=index,
        week=scanner._week_at(metrics, index),
    )
    synthetic = _synthetic_hidden_demand(metrics, index)
    counterfactual = EvidenceResult(
        context=evidence.context,
        evidence=evidence.evidence + (synthetic,),
    )
    original = config.DEMAND_EVIDENCE_WEIGHTS.get(EvidenceCode.HIDDEN_DEMAND)
    config.DEMAND_EVIDENCE_WEIGHTS[EvidenceCode.HIDDEN_DEMAND] = weight
    try:
        candidate = scanner.evaluate(
            trend=trend,
            evidence=counterfactual,
            history=history,
            bar_index=index,
            week=scanner._week_at(metrics, index),
        )
    finally:
        if original is None:
            config.DEMAND_EVIDENCE_WEIGHTS.pop(EvidenceCode.HIDDEN_DEMAND, None)
        else:
            config.DEMAND_EVIDENCE_WEIGHTS[EvidenceCode.HIDDEN_DEMAND] = original
    return baseline, candidate


def _scan_symbol(symbol: str, sample_bars: int, refresh: bool):
    daily = download_data(symbol, refresh=refresh)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    scanner = ScannerEngine()
    engine = EvidenceEngine()
    history = []
    rows = []
    sample_start = max(scanner.MIN_REPLAY_BARS, len(metrics) - sample_bars - max(HORIZONS))

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        evidence = engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=list(trend.structure.structural_swings),
        )
        history.append(evidence)
        if index < sample_start or not _is_hidden_demand(metrics.iloc[index]):
            continue
        context = (trend.structure.state.value, trend.structure.direction.value)
        if context not in PROMOTED_CONTEXTS:
            continue
        if index + max(HORIZONS) >= len(metrics):
            continue

        baseline = scanner.evaluate(
            trend=trend,
            evidence=evidence,
            history=history,
            bar_index=index,
            week=scanner._week_at(metrics, index),
        )
        for weight in WEIGHTS:
            _, candidate = _evaluate(scanner, trend, evidence, history, metrics, index, weight)
            for horizon in HORIZONS:
                outcome = _future_return(metrics, index, horizon)
                if outcome is None:
                    continue
                rows.append(
                    {
                        "symbol": symbol,
                        "index": index,
                        "horizon": horizon,
                        "weight": weight,
                        "baseline_actionable": baseline.actionable,
                        "counterfactual_actionable": candidate.actionable,
                        "baseline_strength": baseline.net_strength,
                        "counterfactual_strength": candidate.net_strength,
                        "outcome": outcome,
                    }
                )
    return rows


def _mean(rows):
    return sum(row["outcome"] for row in rows) / len(rows) if rows else 0.0


def _positive(rows):
    return sum(row["outcome"] > 0.0 for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Outcome audit for HIDDEN_DEMAND-induced actionability changes.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--symbols", nargs="+", default=None)
    args = parser.parse_args()
    if args.sample_bars <= max(HORIZONS):
        raise ValueError("--sample-bars must exceed the maximum horizon")

    symbols = tuple(args.symbols) if args.symbols else SYMBOLS
    rows = []
    failures = []
    for symbol in symbols:
        try:
            rows.extend(_scan_symbol(symbol, args.sample_bars, args.refresh))
        except Exception as exc:
            failures.append((symbol, type(exc).__name__, str(exc)))

    print("=== HIDDEN_DEMAND CHANGED-DECISION OUTCOME AUDIT ===")
    print(f"symbols requested: {len(symbols)}")
    print(f"symbols scanned: {len(symbols) - len(failures)}")
    print(f"promoted contexts: {sorted(PROMOTED_CONTEXTS)}")
    print()
    print(f"{'Weight':>8}{'H':>3}{'Gained':>8}{'Lost':>8}{'Gain Ret':>12}{'Loss Ret':>12}{'Gain Pos':>10}{'Loss Pos':>10}")

    for weight in WEIGHTS:
        for horizon in HORIZONS:
            bucket = [row for row in rows if row["weight"] == weight and row["horizon"] == horizon]
            gained = [row for row in bucket if not row["baseline_actionable"] and row["counterfactual_actionable"]]
            lost = [row for row in bucket if row["baseline_actionable"] and not row["counterfactual_actionable"]]
            print(
                f"{weight:>8.2f}{horizon:>3}{len(gained):>8}{len(lost):>8}"
                f"{_mean(gained):>11.3%}{_mean(lost):>11.3%}"
                f"{_positive(gained):>6}/{len(gained):<3}"
                f"{_positive(lost):>6}/{len(lost):<3}"
            )

    print()
    print("=== CHANGED CASES ===")
    for weight in WEIGHTS:
        changed = [row for row in rows if row["weight"] == weight and row["baseline_actionable"] != row["counterfactual_actionable"]]
        print(f"weight={weight:.2f} changed={len(changed)}")
        for row in changed:
            kind = "GAINED" if row["counterfactual_actionable"] else "LOST"
            print(
                f"  {kind:<6} {row['symbol']:<14} bar={row['index']:<4} H={row['horizon']:<2}"
                f" outcome={row['outcome']:+.3%}"
                f" score={row['baseline_strength']:.4f}->{row['counterfactual_strength']:.4f}"
            )

    if failures:
        print()
        print("=== SCAN FAILURES ===")
        for symbol, error_type, message in failures:
            print(f"{symbol:<16}{error_type}: {message}")


if __name__ == "__main__":
    main()
