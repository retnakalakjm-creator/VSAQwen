"""Audit-only Spring interaction weight calibration.

Replays the validated Spring detector point-in-time, then evaluates the
candidate interaction ``CONFIRMED + LOW_VOLUME_TEST + SHALLOW_PENETRATION``
against candidate bullish evidence weights. No production registry or
scoring configuration is modified by this diagnostic.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config
from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from evidence.spring import SpringValidationResult, detect_spring_candidate, validate_spring
from engine.columns import COL_CLOSE, COL_WEEK
from market_structure.swing_engine import SwingEngine
from market_structure.structure_filter import StructureFilter
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20
FORWARD_HORIZON = 8
SPRING_STRENGTH = 0.90
CANDIDATE_WEIGHTS = (0.25, 0.40, 0.60, 0.75, 0.85, 1.00)

_BULLISH_CODES = {
    "STOPPING_VOLUME", "DEMAND_COMING_IN", "INCREASING_DEMAND",
    "HIDDEN_DEMAND", "DEMAND_DRYING_UP", "STRONG_UPTREND",
    "WEAK_UPTREND", "ACCUMULATION", "REACCUMULATION", "MARKUP",
}
_BEARISH_CODES = {
    "BUYING_CLIMAX", "SUPPLY_COMING_IN", "INCREASING_SUPPLY",
    "HIDDEN_SUPPLY", "SUPPLY_DRYING_UP", "STRONG_DOWNTREND",
    "WEAK_DOWNTREND", "DISTRIBUTION", "REDISTRIBUTION", "MARKDOWN",
}


def _bias_from_difference(difference: float) -> str:
    if difference > config.BACKGROUND_BIAS_MARGIN:
        return "BULLISH"
    if difference < -config.BACKGROUND_BIAS_MARGIN:
        return "BEARISH"
    return "NEUTRAL"


def _bias_difference(evidence) -> float:
    bullish = 0.0
    bearish = 0.0
    for item in evidence:
        code = str(item.code).split(".")[-1].upper()
        weight = 1.0 if item.weight is None else float(item.weight)
        score = weight * float(item.strength)
        if code in _BULLISH_CODES:
            bullish += score
        elif code in _BEARISH_CODES:
            bearish += score
    return bullish - bearish


def _target_interaction(validation) -> bool:
    return (
        validation.confirmation.result == SpringValidationResult.CONFIRMED
        and validation.test.result == SpringValidationResult.TESTED
        and validation.test.volume_ratio is not None
        and validation.test.volume_ratio <= 0.75
        and validation.candidate.penetration_ratio <= 0.50
    )


def _point_in_time_structural_swings(metrics, swings):
    by_confirmation: dict[int, list] = {}
    for swing in swings:
        by_confirmation.setdefault(swing.confirmation_index, []).append(swing)

    confirmed: list = []
    structural: tuple = ()
    for bar_index in range(MIN_REPLAY_BARS, len(metrics) - FORWARD_HORIZON):
        newly_confirmed = by_confirmation.get(bar_index, ())
        if newly_confirmed:
            confirmed.extend(newly_confirmed)
            if len(confirmed) >= 2:
                prefix = metrics.iloc[: bar_index + 1]
                structural = tuple(StructureFilter().filter(confirmed, prefix))
        yield bar_index, structural


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    swings = SwingEngine().calculate(metrics)
    events: list[dict] = []

    for index, structural_swings in _point_in_time_structural_swings(metrics, swings):
        candidate = detect_spring_candidate(
            metrics,
            bar_index=index,
            structural_swings=structural_swings,
        )
        if candidate is None:
            continue

        validation = validate_spring(metrics, candidate=candidate)
        current = float(metrics.iloc[index][COL_CLOSE])
        future_idx = index + FORWARD_HORIZON
        if future_idx >= len(metrics):
            continue
        future = float(metrics.iloc[future_idx][COL_CLOSE])
        if current != current or future != future or current == 0.0:
            continue

        forward_return = (future - current) / current
        outcome = (
            "POSITIVE_8_BAR" if forward_return > 0.02
            else "NEGATIVE_8_BAR" if forward_return < -0.02
            else "FLAT_8_BAR"
        )
        if not _target_interaction(validation):
            continue

        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        evidence = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=tuple(trend.structure.structural_swings),
            validation_metrics=replay,
        )
        baseline_difference = _bias_difference(evidence.evidence)

        events.append({
            "symbol": symbol,
            "bar_index": index,
            "week": str(metrics.iloc[index][COL_WEEK]),
            "outcome": outcome,
            "baseline_bias": _bias_from_difference(baseline_difference),
            "baseline_difference": baseline_difference,
        })

    return events


def _is_bullish_shift(before: str, after: str) -> bool:
    return (before, after) in {
        ("BEARISH", "NEUTRAL"),
        ("BEARISH", "BULLISH"),
        ("NEUTRAL", "BULLISH"),
    }


def _calibrate(rows: list[dict], weight: float) -> dict:
    beneficial = harmful = neutral = no_change = 0
    transitions: dict[str, int] = {}
    by_outcome = {
        "POSITIVE_8_BAR": {"beneficial": 0, "harmful": 0, "neutral": 0, "no_change": 0},
        "NEGATIVE_8_BAR": {"beneficial": 0, "harmful": 0, "neutral": 0, "no_change": 0},
        "FLAT_8_BAR": {"beneficial": 0, "harmful": 0, "neutral": 0, "no_change": 0},
    }

    for row in rows:
        before = row["baseline_bias"]
        delta = weight * SPRING_STRENGTH
        after = _bias_from_difference(row["baseline_difference"] + delta)
        transition = f"{before}->{after}"
        transitions[transition] = transitions.get(transition, 0) + 1

        if before == after:
            no_change += 1
            classification = "no_change"
        elif _is_bullish_shift(before, after):
            if row["outcome"] == "POSITIVE_8_BAR":
                beneficial += 1
                classification = "beneficial"
            elif row["outcome"] == "NEGATIVE_8_BAR":
                harmful += 1
                classification = "harmful"
            else:
                neutral += 1
                classification = "neutral"
        else:
            neutral += 1
            classification = "neutral"

        by_outcome[row["outcome"]][classification] += 1

    return {
        "candidate_weight": weight,
        "events": len(rows),
        "beneficial_changes": beneficial,
        "harmful_changes": harmful,
        "neutral_changes": neutral,
        "no_change": no_change,
        "net_benefit": beneficial - harmful,
        "benefit_harm_ratio": round(beneficial / harmful, 3) if harmful else None,
        "bias_transitions": transitions,
        "by_outcome": by_outcome,
    }


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    rows: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                rows.extend(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    print("SPRING WEIGHT CALIBRATION SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "symbols_with_events": len({x["symbol"] for x in rows}),
        "events": len(rows),
        "spring_strength": SPRING_STRENGTH,
        "candidate_weights": CANDIDATE_WEIGHTS,
        "failures": failures,
    })

    print("SPRING WEIGHT CALIBRATION IMPACT BY WEIGHT")
    for weight in CANDIDATE_WEIGHTS:
        print(_calibrate(rows, weight))


if __name__ == "__main__":
    main()
