from __future__ import annotations

import argparse
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys
from threading import Lock

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
BOOTSTRAP_ITERATIONS = 5000
_CONFIG_LOCK = Lock()


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


def _evaluate_counterfactual(scanner, trend, evidence, history, metrics, index: int, weight: float):
    synthetic = _synthetic_hidden_demand(metrics, index)
    counterfactual = EvidenceResult(
        context=evidence.context,
        evidence=evidence.evidence + (synthetic,),
    )
    with _CONFIG_LOCK:
        original = config.DEMAND_EVIDENCE_WEIGHTS.get(EvidenceCode.HIDDEN_DEMAND)
        config.DEMAND_EVIDENCE_WEIGHTS[EvidenceCode.HIDDEN_DEMAND] = weight
        try:
            return scanner.evaluate(
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


def _scan_symbol(symbol: str, sample_bars: int, refresh: bool) -> list[dict]:
    daily = download_data(symbol, refresh=refresh)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    scanner = ScannerEngine()
    engine = EvidenceEngine()
    history = []
    rows: list[dict] = []
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
            candidate = _evaluate_counterfactual(
                scanner, trend, evidence, history, metrics, index, weight
            )
            changed = baseline.actionable != candidate.actionable
            if not changed:
                continue

            kind = "gained" if candidate.actionable else "lost"
            for horizon in HORIZONS:
                outcome = _future_return(metrics, index, horizon)
                if outcome is None:
                    continue
                rows.append({
                    "symbol": symbol,
                    "index": index,
                    "horizon": horizon,
                    "weight": weight,
                    "kind": kind,
                    "baseline_strength": baseline.net_strength,
                    "counterfactual_strength": candidate.net_strength,
                    "baseline_confidence": baseline.confidence,
                    "counterfactual_confidence": candidate.confidence,
                    "outcome": outcome,
                })
    return rows


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _bootstrap_gain_loss_delta(gained: list[float], lost: list[float], seed: int) -> tuple[float, float, float]:
    if not gained or not lost:
        return 0.0, 0.0, 0.0
    rng = random.Random(seed)
    observed = _mean(gained) - _mean(lost)
    values = []
    for _ in range(BOOTSTRAP_ITERATIONS):
        gain_sample = [gained[rng.randrange(len(gained))] for _ in gained]
        loss_sample = [lost[rng.randrange(len(lost))] for _ in lost]
        values.append(_mean(gain_sample) - _mean(loss_sample))
    values.sort()
    low = values[int(0.025 * BOOTSTRAP_ITERATIONS)]
    high = values[int(0.975 * BOOTSTRAP_ITERATIONS) - 1]
    return observed, low, high


def main() -> None:
    parser = argparse.ArgumentParser(description="HIDDEN_DEMAND changed-decision value robustness audit.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--symbols", nargs="+", default=None)
    args = parser.parse_args()
    if args.sample_bars <= max(HORIZONS):
        raise ValueError("--sample-bars must exceed the maximum horizon")

    symbols = tuple(args.symbols) if args.symbols else SYMBOLS
    rows: list[dict] = []
    failures: list[tuple[str, str, str]] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {
            executor.submit(_scan_symbol, symbol, args.sample_bars, args.refresh): symbol
            for symbol in symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                rows.extend(future.result())
            except Exception as exc:
                failures.append((symbol, type(exc).__name__, str(exc)))

    print("=== HIDDEN_DEMAND CHANGED-DECISION VALUE ROBUSTNESS ===")
    print(f"symbols requested: {len(symbols)}")
    print(f"symbols scanned: {len(symbols) - len(failures)}")
    print(f"promoted contexts: {sorted(PROMOTED_CONTEXTS)}")
    print(f"bootstrap iterations: {BOOTSTRAP_ITERATIONS}")
    print()
    print(f"{'Weight':>8}{'H':>3}{'Gained':>8}{'Lost':>8}{'GainRet':>11}{'LossRet':>11}{'Diff':>10}{'95% Low':>11}{'95% High':>11}{'Robust':>10}")

    for weight in WEIGHTS:
        for horizon in HORIZONS:
            bucket = [r for r in rows if r["weight"] == weight and r["horizon"] == horizon]
            gained = [r["outcome"] for r in bucket if r["kind"] == "gained"]
            lost = [r["outcome"] for r in bucket if r["kind"] == "lost"]
            if not gained or not lost:
                print(f"{weight:>8.2f}{horizon:>3}{len(gained):>8}{len(lost):>8}{_mean(gained):>10.3%}{_mean(lost):>10.3%}")
                continue
            observed, low, high = _bootstrap_gain_loss_delta(
                gained, lost, seed=int(weight * 1000) + horizon
            )
            robust = "positive" if low > 0.0 else "negative" if high < 0.0 else "inconclusive"
            print(
                f"{weight:>8.2f}{horizon:>3}{len(gained):>8}{len(lost):>8}"
                f"{_mean(gained):>10.3%}{_mean(lost):>10.3%}"
                f"{observed:>9.3%}{low:>10.3%}{high:>10.3%}{robust:>12}"
            )

    print()
    print("=== INTERPRETATION RULE ===")
    print("Observed decision value = mean outcome of GAINED cases - mean outcome of LOST cases.")
    print("A fully positive bootstrap interval means the weight's actionability changes favor gains over losses.")
    print("This remains research-only; production scoring and collectors are untouched.")

    if failures:
        print()
        print("=== SCAN FAILURES ===")
        for symbol, error_type, message in failures:
            print(f"{symbol:<16}{error_type}: {message}")


if __name__ == "__main__":
    main()
