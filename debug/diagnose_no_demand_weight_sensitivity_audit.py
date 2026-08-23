"""NO_DEMAND weight sensitivity audit through the production scanner path.

Builds point-in-time Trend/Evidence history once per symbol, then varies only
config.SUPPLY_EVIDENCE_WEIGHTS[NO_DEMAND] during ScannerEngine.evaluate().
Production configuration is restored in finally.
"""
from __future__ import annotations

import os
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config
from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS, COL_WEEK
from evidence.engine import EvidenceEngine
from evidence.profiles import EVIDENCE_REGISTRY
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from scanner import ScannerEngine
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
    "LT.NS",
    "RELIANCE.NS",
    "SBIN.NS",
    "TCS.NS",
)
TARGET_CODE = EvidenceCode.NO_DEMAND
WEIGHTS = (0.40, 0.50, 0.60, 0.70, 0.80, 1.00)
EXPECTED_CANDIDATES = 202
EXPECTED_EVENTS = 109
FORWARD_BARS = 8


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.UP
        and VolumeClass(int(row[COL_VOLUME_CLASS])) <= VolumeClass.LOW
        and SpreadClass(int(row[COL_SPREAD_CLASS])) <= SpreadClass.NARROW
    )


def target_indices(metrics: pd.DataFrame) -> list[int]:
    return [
        i
        for i in range(1, len(metrics) - FORWARD_BARS)
        if cheap_candidate(metrics, i)
    ]


def main() -> None:
    original_weight = config.SUPPLY_EVIDENCE_WEIGHTS[TARGET_CODE]
    registry_weight = EVIDENCE_REGISTRY[TARGET_CODE].weight
    cheap_candidates = 0
    candidate_events = 0
    expensive_history_builds = 0
    target_records: list[tuple[str, int, str | None, object, object, list]] = []
    failures: list[dict[str, str]] = []
    scanner = ScannerEngine()

    try:
        for symbol in SYMBOLS:
            try:
                metrics = MetricsEngine().calculate(
                    daily_to_weekly(download_data(symbol))
                )
                indices = target_indices(metrics)
                cheap_candidates += len(indices)
                if not indices:
                    continue

                max_target = max(indices)
                history = []
                target_set = set(indices)

                for index in range(scanner.MIN_REPLAY_BARS, max_target + 1):
                    replay = metrics.iloc[: index + 1].copy()
                    trend = TrendAnalyzer().analyze(replay)
                    structural_swings = list(trend.structure.structural_swings)
                    evidence = EvidenceEngine().collect(
                        metrics=replay,
                        trend=trend,
                        structural_swings=structural_swings,
                    )
                    history.append(evidence)
                    expensive_history_builds += 1

                    if index not in target_set:
                        continue

                    target_evidence = tuple(
                        item
                        for item in evidence.evidence
                        if item.code is TARGET_CODE and item.bar_index == index
                    )
                    if len(target_evidence) != 1:
                        continue

                    week = metrics.iloc[index].get(COL_WEEK)
                    week_value = None if week is None or pd.isna(week) else str(week)
                    target_records.append(
                        (symbol, index, week_value, trend, evidence, list(history))
                    )
                    candidate_events += 1
            except Exception as exc:
                failures.append({"symbol": symbol, "error": str(exc)})

        results_by_weight: dict[float, list[tuple[str, int, object]]] = {}

        for weight in WEIGHTS:
            config.SUPPLY_EVIDENCE_WEIGHTS[TARGET_CODE] = weight
            weight_results: list[tuple[str, int, object]] = []

            for symbol, index, week, trend, evidence, history in target_records:
                candidate = scanner.evaluate(
                    trend=trend,
                    evidence=evidence,
                    history=history,
                    bar_index=index,
                    week=week,
                )
                weight_results.append((symbol, index, candidate))

            results_by_weight[weight] = weight_results

        reference_weight = original_weight
        if reference_weight not in results_by_weight:
            raise RuntimeError(
                f"configured reference weight {reference_weight} is not in tested weights {WEIGHTS}"
            )

        baseline = results_by_weight[reference_weight]
        baseline_map = {(symbol, index): candidate for symbol, index, candidate in baseline}

        rows: list[dict[str, float | int | bool]] = []
        for weight in WEIGHTS:
            results = results_by_weight[weight]
            score_changed = 0
            actionable_changed = 0
            qualification_changed = 0
            score_deltas: list[float] = []
            strengths: list[float] = []
            confidences: list[float] = []

            for symbol, index, candidate in results:
                base = baseline_map.get((symbol, index))
                if base is None:
                    continue
                delta = candidate.net_strength - base.net_strength
                score_deltas.append(delta)
                strengths.append(candidate.net_strength)
                confidences.append(candidate.confidence)
                if abs(delta) > 1e-12:
                    score_changed += 1
                if candidate.actionable != base.actionable:
                    actionable_changed += 1
                if candidate.qualification != base.qualification:
                    qualification_changed += 1

            rows.append({
                "weight": weight,
                "events": len(results),
                "score_changed_vs_reference": score_changed,
                "actionable_changed_vs_reference": actionable_changed,
                "qualification_changed_vs_reference": qualification_changed,
                "mean_net_strength": sum(strengths) / len(strengths) if strengths else 0.0,
                "mean_confidence": sum(confidences) / len(confidences) if confidences else 0.0,
                "mean_net_strength_delta_vs_reference": sum(score_deltas) / len(score_deltas) if score_deltas else 0.0,
                "candidate_score_mass": sum(strengths),
            })

        failures_out = list(failures)
        if cheap_candidates != EXPECTED_CANDIDATES:
            failures_out.append({
                "scope": "candidate_population",
                "error": f"expected {EXPECTED_CANDIDATES} cheap candidates, got {cheap_candidates}",
            })
        if candidate_events != EXPECTED_EVENTS:
            failures_out.append({
                "scope": "candidate_events",
                "error": f"expected {EXPECTED_EVENTS} emitted events, got {candidate_events}",
            })

        print("NO_DEMAND WEIGHT SENSITIVITY AUDIT")
        print({
            "symbols_requested": len(SYMBOLS),
            "symbols_with_results": len(SYMBOLS) - len(failures),
            "cheap_candidates": cheap_candidates,
            "candidate_events": candidate_events,
            "expected_events": EXPECTED_EVENTS,
            "registry_weight": registry_weight,
            "configured_reference_weight": original_weight,
            "weights_tested": WEIGHTS,
            "reference_weight": reference_weight,
            "production_path_mutation": False,
            "target_replay_built_once_per_symbol": True,
            "expensive_history_builds": expensive_history_builds,
            "failures": failures_out,
            "status": "FAIL" if failures_out else "PASS",
        })
        for row in rows:
            print(row)
    finally:
        config.SUPPLY_EVIDENCE_WEIGHTS[TARGET_CODE] = original_weight


if __name__ == "__main__":
    main()
