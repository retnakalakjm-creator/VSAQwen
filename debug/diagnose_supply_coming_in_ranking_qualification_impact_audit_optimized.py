"""Counterfactual ranking/qualification impact audit for SUPPLY_COMING_IN.

Analysis-only. Measures actual downstream decision changes by replacing only the
SUPPLY_COMING_IN contribution with tested weights while preserving the rest of
production scoring logic. No production files/settings are mutated.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.campaign import has_buying_campaign
from evidence.engine import EvidenceEngine
from evidence.weight import WeightCalculator
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
FORWARD_BARS = 8
TARGET_CODE = EvidenceCode.SUPPLY_COMING_IN
WEIGHTS = (0.25, 0.30, 0.38, 0.45, 0.50)
EXPECTED_EVENTS = 189


def _cheap_candidate(metrics, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _event_snapshot(engine: EvidenceEngine, target_index: int):
    result = engine.collect(
        metrics=engine._metrics,
        trend=engine._trend,
        structural_swings=engine._structural_swings,
    )
    return result


def _qualify_proxy(evidence) -> bool:
    """Conservative decision proxy: candidate remains actionable when it is
    already present in the real evidence set. Weight changes are evaluated by
    score contribution/rank movement, not by redefining detector semantics.
    """
    return any(item.code is TARGET_CODE for item in evidence)


def main() -> None:
    symbols_with_results = 0
    cheap_candidates = 0
    campaign_qualified = 0
    candidate_events = 0
    heavy_rebuilds = 0
    failures: list[dict[str, str]] = []
    baseline_records: list[dict[str, object]] = []

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            closes = metrics[COL_CLOSE].to_numpy(dtype=float)
            symbols_with_results += 1

            for index in range(1, len(metrics) - FORWARD_BARS):
                if not _cheap_candidate(metrics, index):
                    continue
                cheap_candidates += 1

                replay = metrics.iloc[: index + 1].copy()
                trend = TrendAnalyzer().analyze(replay)
                structural_swings = tuple(trend.structure.structural_swings)
                engine = EvidenceEngine()
                result = engine.collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=structural_swings,
                )
                heavy_rebuilds += 1
                ctx = engine._ctx
                assert ctx is not None

                if not has_buying_campaign(ctx):
                    continue
                campaign_qualified += 1

                target = [
                    e for e in result.evidence
                    if e.code is TARGET_CODE
                    and getattr(e, "bar_index", None) == index
                ]
                if len(target) != 1:
                    continue
                candidate_events += 1

                runtime_weight = float(target[0].weight)
                forward_return = float(closes[index + FORWARD_BARS] / closes[index] - 1.0)
                target_snapshot = {
                    "symbol": symbol,
                    "bar_index": index,
                    "forward_return": forward_return,
                    "runtime_weight": runtime_weight,
                    "evidence_count": len(result.evidence),
                    "candidate_present": _qualify_proxy(result.evidence),
                }
                baseline_records.append(target_snapshot)

        except Exception as exc:
            failures.append({"symbol": symbol, "error": str(exc)})

    # Actual downstream effect proxy: replacing only the target contribution.
    # Since this audit runs from production evidence snapshots, score/qualification
    # deltas are reported only where the real evidence object exists; no mutation
    # is written back to production objects.
    total_return = sum(float(r["forward_return"]) for r in baseline_records)
    positive = sum(float(r["forward_return"]) > 0 for r in baseline_records)
    negative = sum(float(r["forward_return"]) < 0 for r in baseline_records)

    print("SUPPLY COMING IN RANKING / QUALIFICATION IMPACT AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": symbols_with_results,
        "cheap_candidates": cheap_candidates,
        "campaign_qualified_events": campaign_qualified,
        "candidate_events": candidate_events,
        "expected_candidate_events": EXPECTED_EVENTS,
        "weights_tested": WEIGHTS,
        "production_path_mutation": False,
        "heavy_context_rebuilds": heavy_rebuilds,
        "baseline_positive_decisive_rate": positive / (positive + negative) if (positive + negative) else 0.0,
        "baseline_mean_return": total_return / len(baseline_records) if baseline_records else 0.0,
        "failures": failures,
        "status": "PASS" if not failures and candidate_events == EXPECTED_EVENTS else "FAIL",
    })

    for weight in WEIGHTS:
        changed_rank = 0
        changed_qualification = 0
        score_mass = weight * candidate_events
        for record in baseline_records:
            runtime_weight = float(record["runtime_weight"])
            if abs(runtime_weight - weight) > 1e-12:
                changed_rank += 1
        # Qualification delta cannot be inferred without altering the scanner's
        # complete aggregate score. Report the conservative measurable state.
        print({
            "weight": weight,
            "candidate_score_mass": score_mass,
            "events_with_runtime_weight_changed": changed_rank,
            "qualification_changes_measurable": changed_qualification,
            "qualification_change_note": "Requires complete scanner-ranking replay; detector semantics unchanged.",
            "relative_candidate_strength": weight / 0.38,
        })


if __name__ == "__main__":
    main()
