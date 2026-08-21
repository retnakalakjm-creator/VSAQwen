"""Full point-in-time scanner replay for SUPPLY_COMING_IN weight calibration.

Analysis-only. Reuses the real ScannerEngine / ProfessionalScoringEngine path
while temporarily overriding only config.SUPPLY_EVIDENCE_WEIGHTS for the
counterfactual weight. The original configuration is restored after each
weight. No repository or production configuration mutation occurs.
"""
from __future__ import annotations

import copy
import os
import sys
from collections import defaultdict
from dataclasses import replace

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config
from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from model.evidence_result_model import EvidenceResult
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from scanner import ScannerCandidate, ScannerEngine, rank_candidates
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
TARGET_CODE = EvidenceCode.SUPPLY_COMING_IN
FORWARD_BARS = 8
MIN_REPLAY_BARS = ScannerEngine.MIN_REPLAY_BARS
WEIGHTS = (0.25, 0.30, 0.38, 0.45, 0.50)
EXPECTED_EVENTS = 189


def _cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _target_indices(metrics: pd.DataFrame) -> list[int]:
    return [
        index
        for index in range(1, len(metrics) - FORWARD_BARS)
        if _cheap_candidate(metrics, index)
    ]


def _build_history(metrics: pd.DataFrame) -> list:
    history = []
    for index in range(MIN_REPLAY_BARS, len(metrics)):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        structural_swings = list(trend.structure.structural_swings)
        evidence = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=structural_swings,
        )
        history.append((index, trend, evidence))
    return history


def _target_event_indices(history: list, target_candidates: set[int]) -> list[int]:
    event_indices: list[int] = []
    for index, _trend, result in history:
        if index not in target_candidates:
            continue
        if any(
            item.code is TARGET_CODE
            and item.bar_index == index
            for item in result.evidence
        ):
            event_indices.append(index)
    return event_indices


def _weighted_config(original: dict, weight: float) -> dict:
    updated = copy.deepcopy(original)
    updated[TARGET_CODE] = weight
    return updated


def _candidate_for_index(
    scanner: ScannerEngine,
    history: list,
    target_index: int,
    trend,
    evidence: EvidenceResult,
    metrics: pd.DataFrame,
) -> ScannerCandidate:
    history_results = [item[2] for item in history if item[0] <= target_index]
    return scanner.evaluate(
        trend=trend,
        evidence=evidence,
        history=history_results,
        bar_index=target_index,
        week=scanner._week_at(metrics, target_index),
    )


def _outcome(metrics: pd.DataFrame, index: int) -> float:
    return float(
        metrics.iloc[index + FORWARD_BARS][COL_CLOSE]
        / metrics.iloc[index][COL_CLOSE]
        - 1.0
    )


def _summary(candidates: list[ScannerCandidate], outcomes: list[float]) -> dict[str, object]:
    actionable = [c for c in candidates if c.actionable]
    positive = sum(v > 0.0 for v in outcomes)
    negative = sum(v < 0.0 for v in outcomes)
    flat = sum(v == 0.0 for v in outcomes)
    return {
        "events": len(candidates),
        "qualified": sum(c.qualification.value != "UNQUALIFIED" for c in candidates),
        "actionable": len(actionable),
        "actionable_rate": len(actionable) / len(candidates) if candidates else 0.0,
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "mean_return": sum(outcomes) / len(outcomes) if outcomes else 0.0,
        "mean_actionable_return": (
            sum(v for c, v in zip(candidates, outcomes) if c.actionable) / len(actionable)
            if actionable else 0.0
        ),
        "mean_net_strength": (
            sum(c.net_strength for c in actionable) / len(actionable)
            if actionable else 0.0
        ),
        "mean_confidence": (
            sum(c.confidence for c in actionable) / len(actionable)
            if actionable else 0.0
        ),
    }


def main() -> None:
    original_weights = copy.deepcopy(config.SUPPLY_EVIDENCE_WEIGHTS)
    prepared: dict[str, dict[str, object]] = {}
    total_events = 0
    heavy_rebuilds = 0
    failures: list[dict[str, str]] = []

    try:
        for symbol in SYMBOLS:
            try:
                metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
                history = _build_history(metrics)
                heavy_rebuilds += len(history)
                cheap = set(_target_indices(metrics))
                events = _target_event_indices(history, cheap)
                prepared[symbol] = {
                    "metrics": metrics,
                    "history": history,
                    "events": events,
                }
                total_events += len(events)
            except Exception as exc:
                failures.append({"symbol": symbol, "error": str(exc)})

        if total_events != EXPECTED_EVENTS:
            failures.append({
                "scope": "population",
                "error": f"expected {EXPECTED_EVENTS} SUPPLY_COMING_IN events, got {total_events}",
            })

        print("SUPPLY COMING IN FULL SCANNER RANKING REPLAY AUDIT")
        print({
            "symbols_requested": len(SYMBOLS),
            "symbols_with_results": len(prepared),
            "candidate_events": total_events,
            "expected_candidate_events": EXPECTED_EVENTS,
            "weights_tested": WEIGHTS,
            "production_path_mutation": False,
            "heavy_context_rebuilds": heavy_rebuilds,
            "failures": failures,
            "status": "FAIL" if failures else "PASS",
        })

        if failures:
            return

        baseline_candidates: dict[str, list[ScannerCandidate]] = defaultdict(list)
        baseline_outcomes: dict[str, list[float]] = defaultdict(list)
        per_weight: dict[float, list[tuple[str, int, ScannerCandidate, float]]] = defaultdict(list)

        scanner = ScannerEngine()

        for weight in WEIGHTS:
            config.SUPPLY_EVIDENCE_WEIGHTS = _weighted_config(original_weights, weight)
            rows = []

            for symbol, data in prepared.items():
                metrics = data["metrics"]
                history = data["history"]
                for target_index in data["events"]:
                    trend = next(t for idx, t, _e in history if idx == target_index)
                    evidence = next(e for idx, _t, e in history if idx == target_index)
                    candidate = _candidate_for_index(
                        scanner,
                        history,
                        target_index,
                        trend,
                        evidence,
                        metrics,
                    )
                    outcome = _outcome(metrics, target_index)
                    per_weight[weight].append((symbol, target_index, candidate, outcome))
                    rows.append((symbol, target_index, candidate, outcome))

                    if weight == WEIGHTS[0]:
                        baseline_candidates[symbol].append(candidate)
                        baseline_outcomes[symbol].append(outcome)

            candidates = [r[2] for r in rows]
            outcomes = [r[3] for r in rows]
            print({
                "weight": weight,
                **_summary(candidates, outcomes),
                "candidate_score_mass": sum(c.base_score for c in candidates),
            })

        # Compare each weight against 0.25 baseline on the same point-in-time events.
        baseline_lookup = {
            (symbol, index): candidate
            for symbol, rows in baseline_candidates.items()
            for index, candidate in zip(prepared[symbol]["events"], rows)
        }

        for weight in WEIGHTS:
            if weight == WEIGHTS[0]:
                continue
            rows = per_weight[weight]
            actionable_changed = 0
            qualification_changed = 0
            rank_position_changed = 0
            score_changed = 0

            for symbol, index, candidate, _outcome_value in rows:
                baseline = baseline_lookup[(symbol, index)]
                if candidate.actionable != baseline.actionable:
                    actionable_changed += 1
                if candidate.qualification != baseline.qualification:
                    qualification_changed += 1
                if abs(candidate.base_score - baseline.base_score) > 1e-12:
                    score_changed += 1

            # Rank within each symbol's target-event cohort. This is a real Scanner rank replay
            # over the same point-in-time candidate objects, but not a full cross-sectional market scan.
            for symbol in prepared:
                base_rows = [
                    r for r in per_weight[WEIGHTS[0]]
                    if r[0] == symbol
                ]
                cur_rows = [
                    r for r in rows
                    if r[0] == symbol
                ]
                base_rank = {
                    (r[0], r[1]): pos
                    for pos, r in enumerate(
                        rank_candidates([r[2] for r in base_rows]),
                        start=1,
                    )
                    for _ in [0]
                }
                cur_ranked = rank_candidates([r[2] for r in cur_rows])
                # Map candidate object identity back to key.
                key_by_id = {id(r[2]): (r[0], r[1]) for r in cur_rows}
                for pos, cand in enumerate(cur_ranked, start=1):
                    key = key_by_id[id(cand)]
                    if base_rank.get(key) != pos:
                        rank_position_changed += 1

            print({
                "weight": weight,
                "vs_baseline_weight": WEIGHTS[0],
                "events": len(rows),
                "score_changed": score_changed,
                "actionable_changed": actionable_changed,
                "qualification_changed": qualification_changed,
                "within_symbol_rank_position_changed": rank_position_changed,
                "full_cross_sectional_market_ranking": False,
                "ranking_note": "This replay ranks the same point-in-time target-event cohort within each symbol. A complete cross-sectional scanner ranking across all symbols/bars would require replaying every scanner candidate at each market date.",
            })

    finally:
        config.SUPPLY_EVIDENCE_WEIGHTS = original_weights


if __name__ == "__main__":
    from metrics_engine import MetricsEngine
    main()
