"""Full point-in-time scanner replay for INCREASING_SUPPLY weight calibration.

Analysis-only. Builds point-in-time scanner history only at bars that can
matter to this audit:
- cheap candidate bars (for target-event scoring), and
- structural swing confirmation bars (for persistent qualification history).

This preserves the production qualification semantics while avoiding an
expensive EvidenceEngine replay for every historical bar.
Production configuration is restored in a finally block.
"""
from __future__ import annotations

import copy
import os
import sys
from collections import defaultdict

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config
from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.engine import EvidenceEngine
from evidence.profiles import EVIDENCE_REGISTRY
from metrics_engine import MetricsEngine
from models import Direction, EvidenceCode, SpreadClass, VolumeClass
from scanner import ScannerCandidate, ScannerEngine, rank_candidates
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
TARGET_CODE = EvidenceCode.INCREASING_SUPPLY
FORWARD_BARS = 8
MIN_REPLAY_BARS = ScannerEngine.MIN_REPLAY_BARS
WEIGHTS = (0.70, 0.75, 0.80, 0.85, 0.90, 1.00)
EXPECTED_EVENTS = 528


def _cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _cheap_candidate_indices(metrics: pd.DataFrame) -> set[int]:
    return {
        index
        for index in range(1, len(metrics) - FORWARD_BARS)
        if _cheap_candidate(metrics, index)
    }


def _structural_confirmation_indices(metrics: pd.DataFrame) -> set[int]:
    """Find structural confirmation bars once; later bars cannot create past confirmations."""
    full_trend = TrendAnalyzer().analyze(metrics)
    confirmations: set[int] = set()
    for structural_swing in full_trend.structure.structural_swings:
        confirmation = getattr(structural_swing.swing, "confirmation_index", None)
        if confirmation is not None:
            confirmations.add(int(confirmation))
    return confirmations


def _build_history(
    metrics: pd.DataFrame,
    replay_indices: set[int],
) -> list[tuple[int, object, object]]:
    """Build reusable point-in-time history only at semantically relevant bars."""
    history: list[tuple[int, object, object]] = []
    for index in sorted(replay_indices):
        if index < MIN_REPLAY_BARS or index >= len(metrics):
            continue
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        evidence = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
        )
        history.append((index, trend, evidence))
    return history


def _target_event_indices(
    history: list[tuple[int, object, object]],
    candidate_set: set[int],
) -> list[int]:
    indices: list[int] = []
    for index, _trend, result in history:
        if index not in candidate_set:
            continue
        if any(
            item.code is TARGET_CODE
            and item.bar_index == index
            for item in result.evidence
        ):
            indices.append(index)
    return indices


def _outcome(metrics: pd.DataFrame, index: int) -> float:
    start = float(metrics.iloc[index][COL_CLOSE])
    end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
    if start == 0.0:
        return 0.0
    return end / start - 1.0


def _evaluate_candidate(
    scanner: ScannerEngine,
    history: list[tuple[int, object, object]],
    target_index: int,
    metrics: pd.DataFrame,
) -> ScannerCandidate:
    target_entry = next(
        (entry for entry in history if entry[0] == target_index),
        None,
    )
    if target_entry is None:
        raise RuntimeError(f"Missing target history snapshot at bar {target_index}")

    trend = target_entry[1]
    evidence = target_entry[2]
    history_results = [entry[2] for entry in history if entry[0] <= target_index]
    return scanner.evaluate(
        trend=trend,
        evidence=evidence,
        history=history_results,
        bar_index=target_index,
        week=scanner._week_at(metrics, target_index),
    )


def _summary(rows: list[tuple[str, int, ScannerCandidate, float]]) -> dict[str, object]:
    candidates = [row[2] for row in rows]
    outcomes = [row[3] for row in rows]
    actionable = [candidate for candidate in candidates if candidate.actionable]
    positive = sum(value > 0.0 for value in outcomes)
    negative = sum(value < 0.0 for value in outcomes)
    flat = sum(value == 0.0 for value in outcomes)
    return {
        "events": len(candidates),
        "qualified": sum(candidate.qualification.value != "UNQUALIFIED" for candidate in candidates),
        "actionable": len(actionable),
        "actionable_rate": len(actionable) / len(candidates) if candidates else 0.0,
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "mean_return": sum(outcomes) / len(outcomes) if outcomes else 0.0,
        "mean_actionable_return": (
            sum(value for candidate, value in zip(candidates, outcomes) if candidate.actionable)
            / len(actionable)
            if actionable else 0.0
        ),
        "mean_net_strength": (
            sum(candidate.net_strength for candidate in actionable) / len(actionable)
            if actionable else 0.0
        ),
        "mean_confidence": (
            sum(candidate.confidence for candidate in actionable) / len(actionable)
            if actionable else 0.0
        ),
        "candidate_score_mass": sum(candidate.base_score for candidate in candidates),
    }


def _rank_map(rows: list[tuple[str, int, ScannerCandidate, float]]) -> dict[tuple[str, int], int]:
    by_symbol: dict[str, list[tuple[str, int, ScannerCandidate, float]]] = defaultdict(list)
    for row in rows:
        by_symbol[row[0]].append(row)

    result: dict[tuple[str, int], int] = {}
    for symbol, symbol_rows in by_symbol.items():
        ranked = rank_candidates([row[2] for row in symbol_rows])
        key_by_id = {id(row[2]): (row[0], row[1]) for row in symbol_rows}
        for position, candidate in enumerate(ranked, start=1):
            result[key_by_id[id(candidate)]] = position
    return result


def _runtime_weight_observed(prepared: dict[str, dict[str, object]]) -> tuple[float, float, float]:
    weights: list[float] = []
    for data in prepared.values():
        history = data["history"]
        events = set(data["events"])
        for index, _trend, result in history:
            if index not in events:
                continue
            weights.extend(
                float(item.weight)
                for item in result.evidence
                if item.code is TARGET_CODE and item.bar_index == index
            )
    if not weights:
        return 0.0, 0.0, 0.0
    return min(weights), max(weights), sum(weights) / len(weights)


def main() -> None:
    original_weights = copy.deepcopy(config.SUPPLY_EVIDENCE_WEIGHTS)
    authoritative_registry_weight = EVIDENCE_REGISTRY[TARGET_CODE].weight
    configured_weight = original_weights[TARGET_CODE]

    prepared: dict[str, dict[str, object]] = {}
    failures: list[dict[str, str]] = []
    history_states_built = 0
    total_events = 0
    total_cheap_candidates = 0

    try:
        for symbol in SYMBOLS:
            try:
                metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
                cheap_set = _cheap_candidate_indices(metrics)
                confirmation_set = _structural_confirmation_indices(metrics)
                replay_indices = cheap_set | confirmation_set
                history = _build_history(metrics, replay_indices)
                history_states_built += len(history)

                events = _target_event_indices(history, cheap_set)
                prepared[symbol] = {
                    "metrics": metrics,
                    "history": history,
                    "events": events,
                }
                total_cheap_candidates += len(cheap_set)
                total_events += len(events)
            except Exception as exc:
                failures.append({"symbol": symbol, "error": str(exc)})

        observed_min, observed_max, observed_mean = _runtime_weight_observed(prepared)

        print("INCREASING SUPPLY FULL SCANNER RANKING REPLAY AUDIT")
        print({
            "symbols_requested": len(SYMBOLS),
            "symbols_with_results": len(prepared),
            "cheap_candidates": total_cheap_candidates,
            "candidate_events": total_events,
            "expected_candidate_events": EXPECTED_EVENTS,
            "registry_weight": authoritative_registry_weight,
            "configured_supply_map_weight": configured_weight,
            "runtime_weight_observed": {
                "min": observed_min,
                "max": observed_max,
                "mean": observed_mean,
            },
            "weights_tested": WEIGHTS,
            "production_path_mutation": False,
            "history_states_built": history_states_built,
            "history_strategy": "cheap_candidates_plus_structural_confirmation_bars",
            "history_built_once_per_symbol": True,
            "failures": failures,
            "status": "FAIL" if failures or total_events != EXPECTED_EVENTS else "PASS",
        })

        if failures or total_events != EXPECTED_EVENTS:
            return

        scanner = ScannerEngine()
        results_by_weight: dict[float, list[tuple[str, int, ScannerCandidate, float]]] = {}

        for weight in WEIGHTS:
            config.SUPPLY_EVIDENCE_WEIGHTS = copy.deepcopy(original_weights)
            config.SUPPLY_EVIDENCE_WEIGHTS[TARGET_CODE] = weight

            rows: list[tuple[str, int, ScannerCandidate, float]] = []
            for symbol, data in prepared.items():
                metrics = data["metrics"]
                for target_index in data["events"]:
                    candidate = _evaluate_candidate(
                        scanner,
                        data["history"],
                        target_index,
                        metrics,
                    )
                    rows.append((symbol, target_index, candidate, _outcome(metrics, target_index)))

            results_by_weight[weight] = rows
            print({"weight": weight, **_summary(rows)})

        baseline_weight = WEIGHTS[0]
        baseline = results_by_weight[baseline_weight]
        baseline_lookup = {
            (symbol, index): candidate
            for symbol, index, candidate, _outcome_value in baseline
        }
        baseline_rank = _rank_map(baseline)

        for weight in WEIGHTS[1:]:
            rows = results_by_weight[weight]
            actionable_changed = 0
            qualification_changed = 0
            score_changed = 0

            for symbol, index, candidate, _outcome_value in rows:
                base = baseline_lookup[(symbol, index)]
                actionable_changed += int(candidate.actionable != base.actionable)
                qualification_changed += int(candidate.qualification != base.qualification)
                score_changed += int(abs(candidate.base_score - base.base_score) > 1e-12)

            current_rank = _rank_map(rows)
            rank_changed = sum(
                1
                for key, position in current_rank.items()
                if position != baseline_rank.get(key)
            )

            print({
                "weight": weight,
                "vs_baseline_weight": baseline_weight,
                "events": len(rows),
                "score_changed": score_changed,
                "actionable_changed": actionable_changed,
                "qualification_changed": qualification_changed,
                "within_symbol_rank_position_changed": rank_changed,
                "full_cross_sectional_market_ranking": False,
            })

    finally:
        config.SUPPLY_EVIDENCE_WEIGHTS = original_weights


if __name__ == "__main__":
    main()
