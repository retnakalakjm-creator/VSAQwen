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
WEIGHTS = (0.00, 0.10, 0.15, 0.20, 0.25, 0.30)


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
        observation="Synthetic HIDDEN_DEMAND for counterfactual scoring audit.",
        description="Counterfactual HIDDEN_DEMAND event; production collector is unchanged.",
        bar_index=index,
        week_beginning=str(week),
    )


def _scan_symbol(symbol: str, sample_bars: int, refresh: bool) -> list[tuple[float, float, float, bool, bool]]:
    daily = download_data(symbol, refresh=refresh)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    scanner = ScannerEngine()
    engine = EvidenceEngine()
    history = []
    rows: list[tuple[float, float, float, bool, bool]] = []
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

        baseline = scanner.evaluate(
            trend=trend,
            evidence=evidence,
            history=history,
            bar_index=index,
            week=scanner._week_at(metrics, index),
        )
        for weight in WEIGHTS:
            if weight == 0.0:
                candidate = baseline
            else:
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
            rows.append((
                weight,
                candidate.net_strength - baseline.net_strength,
                candidate.confidence - baseline.confidence,
                baseline.actionable,
                candidate.actionable,
            ))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Real production-path HIDDEN_DEMAND actionability safety audit.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--symbols", nargs="+", default=None)
    args = parser.parse_args()
    if args.sample_bars <= max(HORIZONS):
        raise ValueError("--sample-bars must exceed the maximum horizon")

    symbols = tuple(args.symbols) if args.symbols else SYMBOLS
    rows: list[tuple[float, float, float, bool, bool]] = []
    failures: list[tuple[str, str, str]] = []
    for symbol in symbols:
        try:
            rows.extend(_scan_symbol(symbol, args.sample_bars, args.refresh))
        except Exception as exc:
            failures.append((symbol, type(exc).__name__, str(exc)))

    print("=== HIDDEN_DEMAND ACTIONABILITY SAFETY AUDIT ===")
    print(f"symbols requested: {len(symbols)}")
    print(f"symbols scanned: {len(symbols) - len(failures)}")
    print(f"promoted contexts: {sorted(PROMOTED_CONTEXTS)}")
    print()
    print(f"{'Weight':>8}{'Events':>8}{'Mean dStrength':>16}{'Mean dConfidence':>18}{'Actionable 0':>14}{'Actionable 1':>14}{'Gained':>10}{'Lost':>8}")
    for weight in WEIGHTS:
        bucket = [row for row in rows if row[0] == weight]
        if not bucket:
            continue
        mean_strength_delta = sum(row[1] for row in bucket) / len(bucket)
        mean_confidence_delta = sum(row[2] for row in bucket) / len(bucket)
        gained = sum(not baseline and after for _, _, _, baseline, after in bucket)
        lost = sum(baseline and not after for _, _, _, baseline, after in bucket)
        base_count = sum(row[3] for row in bucket)
        after_count = sum(row[4] for row in bucket)
        print(
            f"{weight:>8.2f}{len(bucket):>8}"
            f"{mean_strength_delta:>16.4f}{mean_confidence_delta:>18.4f}"
            f"{base_count:>14}{after_count:>14}{gained:>10}{lost:>8}"
        )

    if failures:
        print()
        print("=== SCAN FAILURES ===")
        for symbol, error_type, message in failures:
            print(f"{symbol:<16}{error_type}: {message}")


if __name__ == "__main__":
    main()
