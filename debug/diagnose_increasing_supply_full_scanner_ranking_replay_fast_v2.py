"""Fast INCREASING_SUPPLY scanner ranking replay.

Phase 1 (weight-independent):
- identify the frozen cheap-candidate dates;
- build one full TrendAnalyzer result per symbol for structural provenance;
- build one target-bar TrendAnalyzer + EvidenceEngine result per emitted target event;
- derive the chronological structural-progression history once per symbol.

Phase 2 (weight-dependent):
- clone cached target Evidence objects;
- rewrite only INCREASING_SUPPLY.weight;
- run ScannerEngine.evaluate() for each tested weight.

Production configuration is restored in finally.
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


def cheap_candidate(metrics: pd.DataFrame, index: int) -> bool:
    row = metrics.iloc[index]
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def candidate_indices(metrics: pd.DataFrame) -> list[int]:
    return [
        i for i in range(1, len(metrics) - FORWARD_BARS)
        if cheap_candidate(metrics, i)
    ]


def outcome(metrics: pd.DataFrame, index: int) -> float:
    start = float(metrics.iloc[index][COL_CLOSE])
    end = float(metrics.iloc[index + FORWARD_BARS][COL_CLOSE])
    return 0.0 if start == 0.0 else end / start - 1.0


def reweight_target(result: EvidenceResult, weight: float) -> EvidenceResult:
    """Clone evidence so only INCREASING_SUPPLY receives the tested weight."""
    evidence = tuple(
        replace(item, weight=weight) if item.code is TARGET_CODE else item
        for item in result.evidence
    )
    return EvidenceResult(context=result.context, evidence=evidence)


def build_structural_history(metrics: pd.DataFrame, full_trend) -> list[EvidenceResult]:
    """Build the exact chronological structural-progression events used for qualification."""
    structural_swings = tuple(full_trend.structure.structural_swings)
    events: list[Evidence] = []

    for position, structural_swing in enumerate(structural_swings):
        prefix = structural_swings[: position + 1]
        _progression, difference = calculate_professional_progression(prefix)
        if difference is None:
            continue

        strength = min(abs(difference) * 5.0, 1.0)
        confirmation = int(structural_swing.swing.confirmation_index)

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

        week = metrics.iloc[confirmation].get("week_beginning", "")
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
                week_beginning=str(week),
            )
        )

    events.sort(key=lambda item: item.bar_index)
    return [
        EvidenceResult(context=None, evidence=(event,))
        for event in events
    ]


def history_until(structural_history: list[EvidenceResult], target_index: int, context) -> list[EvidenceResult]:
    """Reuse structural progression history up to the target bar."""
    return [
        EvidenceResult(context=context, evidence=result.evidence)
        for result in structural_history
        if result.evidence and result.evidence[0].bar_index <= target_index
    ]


def summary(rows: list[tuple[str, int, ScannerCandidate, float]]) -> dict[str, object]:
    candidates = [r[2] for r in rows]
    returns = [r[3] for r in rows]
    actionable = [c for c in candidates if c.actionable]
    return {
        "events": len(candidates),
        "qualified": sum(c.qualification.value != "UNQUALIFIED" for c in candidates),
        "actionable": len(actionable),
        "actionable_rate": len(actionable) / len(candidates) if candidates else 0.0,
        "positive": sum(x > 0.0 for x in returns),
        "negative": sum(x < 0.0 for x in returns),
        "flat": sum(x == 0.0 for x in returns),
        "mean_return": sum(returns) / len(returns) if returns else 0.0,
        "mean_actionable_return": (
            sum(r for c, r in zip(candidates, returns) if c.actionable) / len(actionable)
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
        "candidate_score_mass": sum(c.base_score for c in candidates),
    }


def rank_map(rows: list[tuple[str, int, ScannerCandidate, float]]) -> dict[tuple[str, int], int]:
    grouped: dict[str, list[tuple[str, int, ScannerCandidate, float]]] = defaultdict(list)
    for row in rows:
        grouped[row[0]].append(row)

    result: dict[tuple[str, int], int] = {}
    for symbol, symbol_rows in grouped.items():
        ranked = rank_candidates([r[2] for r in symbol_rows])
        by_id = {id(r[2]): (r[0], r[1]) for r in symbol_rows}
        for position, candidate in enumerate(ranked, start=1):
            result[by_id[id(candidate)]] = position
    return result


def main() -> None:
    original_weights = copy.deepcopy(config.SUPPLY_EVIDENCE_WEIGHTS)
    registry_weight = EVIDENCE_REGISTRY[TARGET_CODE].weight
    configured_weight = original_weights[TARGET_CODE]

    prepared: dict[str, dict[str, object]] = {}
    failures: list[dict[str, str]] = []
    target_replays = 0
    total_cheap = 0
    total_events = 0

    try:
        # Phase 1: everything here is independent of the tested weight.
        for symbol in SYMBOLS:
            try:
                metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
                indices = candidate_indices(metrics)
                total_cheap += len(indices)

                full_trend = TrendAnalyzer().analyze(metrics)
                structural_history = build_structural_history(metrics, full_trend)

                snapshots: dict[int, tuple[object, EvidenceResult]] = {}
                event_indices: list[int] = []

                for index in indices:
                    replay = metrics.iloc[: index + 1].copy()
                    trend = TrendAnalyzer().analyze(replay)
                    result = EvidenceEngine().collect(
                        metrics=replay,
                        trend=trend,
                        structural_swings=tuple(trend.structure.structural_swings),
                    )
                    snapshots[index] = (trend, result)
                    target_replays += 1

                    if any(
                        item.code is TARGET_CODE and item.bar_index == index
                        for item in result.evidence
                    ):
                        event_indices.append(index)

                prepared[symbol] = {
                    "metrics": metrics,
                    "full_trend": full_trend,
                    "structural_history": structural_history,
                    "snapshots": snapshots,
                    "events": event_indices,
                }
                total_events += len(event_indices)
            except Exception as exc:
                failures.append({"symbol": symbol, "error": str(exc)})

        print("INCREASING SUPPLY FULL SCANNER RANKING REPLAY FAST V2")
        print({
            "symbols_requested": len(SYMBOLS),
            "symbols_with_results": len(prepared),
            "cheap_candidates": total_cheap,
            "candidate_events": total_events,
            "expected_candidate_events": EXPECTED_EVENTS,
            "registry_weight": registry_weight,
            "configured_supply_map_weight": configured_weight,
            "weights_tested": WEIGHTS,
            "weight_independent_target_replays": target_replays,
            "weight_dependent_scoring_replays": total_events * len(WEIGHTS),
            "production_path_mutation": False,
            "cached_evidence_reweighted_per_weight": True,
            "structural_history_reused_per_weight": True,
            "failures": failures,
            "status": "FAIL" if failures or total_events != EXPECTED_EVENTS else "PASS",
        })

        if failures or total_events != EXPECTED_EVENTS:
            return

        # Phase 2: only clone/reweight cached target evidence and score.
        scanner = ScannerEngine()
        results_by_weight: dict[float, list[tuple[str, int, ScannerCandidate, float]]] = {}

        for weight in WEIGHTS:
            rows: list[tuple[str, int, ScannerCandidate, float]] = []
            for symbol, data in prepared.items():
                metrics = data["metrics"]
                structural_history = data["structural_history"]
                snapshots = data["snapshots"]

                for index in data["events"]:
                    trend, frozen_result = snapshots[index]
                    target_result = reweight_target(frozen_result, weight)
                    history = history_until(structural_history, index, target_result.context)

                    candidate = scanner.evaluate(
                        trend=trend,
                        evidence=target_result,
                        history=history,
                        bar_index=index,
                        week=scanner._week_at(metrics, index),
                    )
                    rows.append((symbol, index, candidate, outcome(metrics, index)))

            results_by_weight[weight] = rows
            print({"weight": weight, **summary(rows)})

        baseline_weight = WEIGHTS[0]
        baseline = results_by_weight[baseline_weight]
        baseline_lookup = {(s, i): c for s, i, c, _ in baseline}
        baseline_rank = rank_map(baseline)

        for weight in WEIGHTS[1:]:
            rows = results_by_weight[weight]
            score_changed = actionable_changed = qualification_changed = 0
            for symbol, index, candidate, _ in rows:
                base = baseline_lookup[(symbol, index)]
                score_changed += int(abs(candidate.base_score - base.base_score) > 1e-12)
                actionable_changed += int(candidate.actionable != base.actionable)
                qualification_changed += int(candidate.qualification != base.qualification)

            current_rank = rank_map(rows)
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
