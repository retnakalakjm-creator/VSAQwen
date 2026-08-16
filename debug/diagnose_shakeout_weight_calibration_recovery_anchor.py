from __future__ import annotations

import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.campaign import has_selling_campaign, validate_shakeout
from evidence.engine import EvidenceEngine
from evidence.rules import has_strong_spread, is_bearish_bar, is_very_high_volume, makes_lower_low
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from professional.scoring_engine import ProfessionalScoringEngine
from trend import TrendAnalyzer

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20
WEIGHTS = (0.50, 0.60, 0.70, 0.80, 0.90, 1.00)


def candidate_indices(metrics) -> list[int]:
    out: list[int] = []
    for index in range(MIN_REPLAY_BARS, len(metrics)):
        row = metrics.iloc[index]
        if (
            Direction(int(row[COL_DIRECTION])) == Direction.DOWN
            and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.VERY_HIGH
            and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.WIDE
        ):
            out.append(index)
    return out


def confirmed_shakeouts(metrics, symbol: str) -> list[dict]:
    events: list[dict] = []
    for candidate_index in candidate_indices(metrics):
        replay = metrics.iloc[: candidate_index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)
        engine = EvidenceEngine()
        engine.collect(metrics=replay, trend=trend, structural_swings=structural_swings)
        ctx = engine._ctx
        if ctx is None or ctx.previous is None:
            continue
        bar = ctx.current
        previous = ctx.previous
        if not (
            has_selling_campaign(ctx)
            and is_bearish_bar(bar)
            and has_strong_spread(bar)
            and is_very_high_volume(bar)
            and makes_lower_low(bar, previous)
        ):
            continue
        validation = validate_shakeout(metrics=metrics, shakeout_index=candidate_index)
        recovery_index = validation.recovery.recovery_index
        if recovery_index is None:
            continue
        recovery_index = int(recovery_index)
        events.append({
            "symbol": symbol,
            "candidate_index": candidate_index,
            "recovery_index": recovery_index,
            "quality": float(__import__('evidence.demand', fromlist=['calculate_shakeout_quality']).calculate_shakeout_quality(validation=validation)),
        })
    return events


def decision_snapshot(*, trend, evidence_result, weight: float) -> float:
    # Measure only the SHAKEOUT contribution to net strength as a controlled
    # counterfactual, leaving all other evidence unchanged.
    scoring_items = []
    for item in evidence_result.evidence:
        if item.code is EvidenceCode.SHAKEOUT:
            scoring_items.append(item)
    if not scoring_items:
        return 0.0
    from dataclasses import replace
    counterfactual = tuple(
        replace(item, weight=weight)
        for item in scoring_items
    )
    from model.evidence_result_model import EvidenceResult
    result = EvidenceResult(
        context=evidence_result.context,
        evidence=counterfactual,
    )
    professional = ProfessionalScoringEngine().calculate(
        trend=trend,
        evidence=result,
    )
    return float(professional.scores.net_strength)


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    events = confirmed_shakeouts(metrics, symbol)
    rows: list[dict] = []
    for event in events:
        idx = event["recovery_index"]
        replay = metrics.iloc[: idx + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = tuple(trend.structure.structural_swings)
        evidence = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )
        actual = decision_snapshot(trend=trend, evidence_result=evidence, weight=0.0)
        snapshots = {}
        for weight in WEIGHTS:
            snapshots[f"{weight:.2f}"] = decision_snapshot(
                trend=trend,
                evidence_result=evidence,
                weight=weight,
            )
        rows.append({
            **event,
            "baseline_without_shakeout": actual,
            "candidate_weight_strength": snapshots,
        })
    return rows


def classify_counterfactual(rows: list[dict], weight_key: str) -> dict:
    beneficial = harmful = unchanged = 0
    magnitudes_beneficial: list[float] = []
    magnitudes_harmful: list[float] = []
    for row in rows:
        base = float(row["baseline_without_shakeout"])
        candidate = float(row["candidate_weight_strength"][weight_key])
        if candidate > base:
            beneficial += 1
            magnitudes_beneficial.append(candidate - base)
        elif candidate < base:
            harmful += 1
            magnitudes_harmful.append(base - candidate)
        else:
            unchanged += 1
    return {
        "beneficial_decision_changes": beneficial,
        "harmful_decision_changes": harmful,
        "unchanged": unchanged,
        "net_benefit": beneficial - harmful,
        "benefit_harm_ratio": (beneficial / harmful) if harmful else float("inf"),
    }


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_rows: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                all_rows.extend(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("SHAKEOUT RECOVERY-ANCHOR WEIGHT CALIBRATION SUMMARY")
    print({"events": len(all_rows), "symbols_with_events": len({r['symbol'] for r in all_rows}), "failures": failures})

    for weight in WEIGHTS:
        key = f"{weight:.2f}"
        stats = classify_counterfactual(all_rows, key)
        print({"weight": weight, **stats})

    print("SHAKEOUT RECOVERY-ANCHOR WEIGHT CALIBRATION LEAVE_ONE_OUT")
    for excluded in symbols:
        rows = [r for r in all_rows if r["symbol"] != excluded]
        per_weight = []
        for weight in WEIGHTS:
            key = f"{weight:.2f}"
            per_weight.append({"weight": weight, **classify_counterfactual(rows, key)})
        print({"excluded_symbol": excluded, "events": len(rows), "weights": per_weight})

    print("SHAKEOUT RECOVERY-ANCHOR WEIGHT CALIBRATION EVENTS")
    for row in all_rows:
        print(row)


if __name__ == "__main__":
    main()
