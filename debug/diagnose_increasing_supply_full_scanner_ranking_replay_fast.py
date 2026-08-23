"""Fast point-in-time scanner replay for INCREASING_SUPPLY weight calibration.

Analysis-only.

Optimization:
- identify the frozen cheap-candidate dates directly from metrics;
- build each target bar's point-in-time TrendResult + EvidenceResult exactly once;
- derive chronological structural-progression history without rebuilding
  EvidenceEngine for every historical bar;
- vary only config.SUPPLY_EVIDENCE_WEIGHTS[target_code] during the cheap
  scanner/scoring replay;
- restore production configuration in finally.

The expensive TrendAnalyzer + EvidenceEngine target replay is therefore
O(target events), not O(weights * target events).
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
from market_structure.progression import calculate_professional_progression
from metrics_engine import MetricsEngine
from model.evidence_result_model import EvidenceResult
from models import (
    Direction,
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    SpreadClass,
    VolumeClass,
)
from scanner import ScannerCandidate, ScannerEngine, rank_candidates
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS",
    "LT.NS", "RELIANCE.NS", "SBIN.NS", "TCS.NS",
)
TARGET_CODE = EvidenceCode.INCREASING_SUPPLY
FORWARD_BARS = 8
WEIGHTS = (0.70, 0.75, 0.80, 0.85, 0.90, 1.00)
EXPECTED_EVENTS = 528


def _cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _candidate_indices(metrics: pd.DataFrame) -> list[int]:
    return [
        index
        for index in range(1, len(metrics) - FORWARD_BARS)
        if _cheap_candidate(metrics, index)
    ]


def _build_structural_history(
    metrics: pd.DataFrame,
    full_trend,
) -> list[tuple[int, EvidenceResult]]:
    """Derive structural progression events from confirmed swings only."""
    structural_swings = tuple(full_trend.structure.structural_swings)
    events: list[Evidence] = []

    for position, structural_swing in enumerate(structural_swings):
        confirmation = int(structural_swing.swing.confirmation_index)
        prefix = structural_swings[: position + 1]
        _progression, difference = calculate_professional_progression(prefix)

        if difference is None:
            continue

        strength = min(abs(difference) * 5.0, 1.0)

        if difference >= config.PROGRESSION_NEUTRAL_MARGIN:
            code = EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING
            direction = EvidenceDirection.BULLISH
            observation = "Professional structural progression improving"
            description = "Recent structural swing quality is stronger than the previous campaign."
        elif difference <= -config.PROGRESSION_NEUTRAL_MARGIN:
            code = EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING
            direction = EvidenceDirection.BEARISH
            observation = "Professional structural progression weakening"
            description = "Recent structural swing quality is weaker than the previous campaign."
        else:
            continue

        week_beginning = metrics.iloc[confirmation].get("week_beginning", "")
        events.append(
            Evidence(
                code=code,
                category=EvidenceCategory.TREND,
                direction=direction,
                strength=strength,
                weight=1.0,
                observation=observation,
                description=description,
                bar_index=confirmation,
                week_beginning=str(week_beginning),
            )
        )

    events.sort(key=lambda item: item.bar_index)
    return [
        (event.bar_index, EvidenceResult(context=None, evidence=(event,)))
        for event in events
    ]


def _history_until(
    structural_history: list[tuple[int, EvidenceResult]],
    target_index: int,
    context,
) -> list[EvidenceResult]:
    return [
        EvidenceResult(context=context, evidence=result.evidence)
        for bar_index, result in structural_history
        if bar_index <= target_index
    ]


def _outcome(metrics: pd.DataFrame, index: int) -> float:
    start = float(metrics.iloc[index][COL_CLOSE])
    end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
    if start == 0.0:
        return 0.0
    return end / start - 1.0


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


def _prepare_targets(
    metrics: pd.DataFrame,
    target_indices: list[int],
    structural_history: list[tuple[int, EvidenceResult]],
) -> list[tuple[int, object, EvidenceResult, list[EvidenceResult], float]]:
    """Build every expensive target snapshot once, independent of weight."""
    prepared: list[tuple[int, object, EvidenceResult, list[EvidenceResult], float]] = []
    for target_index in target_indices:
        replay = metrics.iloc[: target_index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        collected = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
        )
        target_result = EvidenceResult(
            context=collected.context,
            evidence=collected.evidence,
        )
        history = _history_until(
            structural_history,
            target_index,
            collected.context,
        )
        prepared.append(
            (
                target_index,
                trend,
                target_result,
                history,
                _outcome(metrics, target_index),
            )
        )
    return prepared


def main() -> None:
    original_weights = copy.deepcopy(config.SUPPLY_EVIDENCE_WEIGHTS)
    registry_weight = EVIDENCE_REGISTRY[TARGET_CODE].weight
    configured_weight = original_weights[TARGET_CODE]

    prepared: dict[str, dict[str, object]] = {}
    failures: list[dict[str, str]] = []
    target_replays = 0
    total_events = 0
    total_cheap = 0

    try:
        # Phase 1: all expensive market-data / trend / evidence preparation.
        # This phase has no weight loop.
        for symbol in SYMBOLS:
            try:
                metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
                target_indices = _candidate_indices(metrics)
                full_trend = TrendAnalyzer().analyze(metrics)
                structural_history = _build_structural_history(metrics, full_trend)
                targets = _prepare_targets(metrics, target_indices, structural_history)

                emitted_target_indices = [
                    index
                    for index, _trend, result, _history, _outcome in targets
                    if any(
                        item.code is TARGET_CODE and item.bar_index == index
                        for item in result.evidence
                    )
                ]

                prepared[symbol] = {
                    "metrics": metrics,
                    "targets": [
                        target
                        for target in targets
                        if target[0] in set(emitted_target_indices)
                    ],
                }
                total_cheap += len(target_indices)
                total_events += len(emitted_target_indices)
            except Exception as exc:
                failures.append({"symbol": symbol, "error": str(exc)})

        if total_events != EXPECTED_EVENTS:
            failures.append({
                "scope": "population",
                "error": f"expected {EXPECTED_EVENTS} events, got {total_events}",
            })

        print("INCREASING SUPPLY FULL SCANNER RANKING REPLAY FAST AUDIT")
        print({
            "symbols_requested": len(SYMBOLS),
            "symbols_with_results": len(prepared),
            "cheap_candidates": total_cheap,
            "candidate_events": total_events,
            "expected_candidate_events": EXPECTED_EVENTS,
            "registry_weight": registry_weight,
            "configured_supply_map_weight": configured_weight,
            "weights_tested": WEIGHTS,
            "target_replays": sum(len(data["targets"]) for data in prepared.values()),
            "weight_replays": sum(len(data["targets"]) for data in prepared.values()) * len(WEIGHTS),
            "production_path_mutation": False,
            "expensive_target_replay_weight_independent": True,
            "failures": failures,
            "status": "FAIL" if failures else "PASS",
        })

        if failures:
            return

        scanner = ScannerEngine()
        results_by_weight: dict[float, list[tuple[str, int, ScannerCandidate, float]]] = {}

        # Phase 2: only scanner/scoring is repeated for each counterfactual weight.
        for weight in WEIGHTS:
            config.SUPPLY_EVIDENCE_WEIGHTS = copy.deepcopy(original_weights)
            config.SUPPLY_EVIDENCE_WEIGHTS[TARGET_CODE] = weight

            rows: list[tuple[str, int, ScannerCandidate, float]] = []
            for symbol, data in prepared.items():
                metrics = data["metrics"]
                for target_index, trend, target_result, history, outcome in data["targets"]:
                    candidate = scanner.evaluate(
                        trend=trend,
                        evidence=target_result,
                        history=history,
                        bar_index=target_index,
                        week=scanner._week_at(metrics, target_index),
                    )
                    rows.append((symbol, target_index, candidate, outcome))

            results_by_weight[weight] = rows
            print({"weight": weight, **_summary(rows)})

        baseline_weight = WEIGHTS[0]
        baseline = results_by_weight[baseline_weight]
        baseline_lookup = {(symbol, index): candidate for symbol, index, candidate, _ in baseline}
        baseline_rank = _rank_map(baseline)

        for weight in WEIGHTS[1:]:
            rows = results_by_weight[weight]
            actionable_changed = qualification_changed = score_changed = 0

            for symbol, index, candidate, _ in rows:
                base = baseline_lookup[(symbol, index)]
                actionable_changed += int(candidate.actionable != base.actionable)
                qualification_changed += int(candidate.qualification != base.qualification)
                score_changed += int(abs(candidate.base_score - base.base_score) > 1e-12)

            current_rank = _rank_map(rows)
            rank_changed = sum(
                int(position != baseline_rank.get(key))
                for key, position in current_rank.items()
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
