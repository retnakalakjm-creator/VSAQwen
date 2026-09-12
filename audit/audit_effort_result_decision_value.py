"""Audit point-in-time Effort vs Result decision value against forward outcomes.

This module is audit/report only. It summarizes cohorts and readiness signals
without changing detector activation, scoring, ranking, actionability, scanner
state, persistence, or any broker/order behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

RELATION = {
    "high_effort_low_result": lambda e, r: e >= 1.5 and r < 1.0,
    "high_effort_normal_result": lambda e, r: e >= 1.5 and 1.0 <= r < 1.5,
    "high_effort_high_result": lambda e, r: e >= 1.5 and r >= 1.5,
    "normal_effort_low_result": lambda e, r: 0.75 <= e < 1.5 and r < 1.0,
    "normal_effort_high_result": lambda e, r: 0.75 <= e < 1.5 and r >= 1.5,
    "low_effort_high_result": lambda e, r: e < 0.75 and r >= 1.5,
    "low_effort_normal_result": lambda e, r: e < 0.75 and 1.0 <= r < 1.5,
    "low_effort_low_result": lambda e, r: e < 0.75 and r < 1.0,
}

EVENTS = (
    "NO_DEMAND",
    "NO_SUPPLY",
    "STOPPING_VOLUME",
    "BUYING_CLIMAX",
    "SUPPLY_COMING_IN",
    "UPTHRUST",
)

EFFORT_RESULT_EVENTS = (
    "EFFORT_GT_RESULT",
    "RESULT_GT_EFFORT",
    "ABSORPTION",
    "EFFORT_RESULT",
)

READINESS_SCOPES = frozenset(
    {
        "effort_result_event",
        "effort_result_event_plus_relationship",
    }
)
READINESS_CANDIDATE = "candidate_for_calibration_review"
READINESS_INSUFFICIENT_SAMPLE = "insufficient_sample"
READINESS_OBSERVATION_ONLY = "observation_only"
MIN_READINESS_BARS = 10
MIN_READINESS_ABS_DELTA = 0.005

OUTCOME_COLUMNS = (
    "symbol",
    "bar_index",
    "relationship",
    "events",
    "horizon",
    "forward_return",
    "forward_up",
)


def events(value: object) -> set[str]:
    if not isinstance(value, str) or not value.strip():
        return set()
    try:
        raw = json.loads(value)
    except json.JSONDecodeError:
        return set()
    out = set()
    for item in raw if isinstance(raw, list) else []:
        code = (
            item
            if isinstance(item, str)
            else item.get("code")
            if isinstance(item, dict)
            else None
        )
        if code:
            out.add(str(code).rsplit(".", 1)[-1].upper())
    return out


def classify(effort: float, result: float) -> str:
    for name, predicate in RELATION.items():
        if predicate(effort, result):
            return name
    return "unclassified"


def decision_value_readiness(
    comparisons: Iterable[Mapping[str, Any]],
    *,
    min_bars: int = MIN_READINESS_BARS,
    min_abs_delta: float = MIN_READINESS_ABS_DELTA,
) -> list[dict[str, object]]:
    """Classify Effort/Result audit cohorts before any production weighting.

    A positive readiness status is permission to review a cohort, not permission
    to change scoring, ranking, actionability, or detector behavior.
    """

    if min_bars <= 0:
        raise ValueError("min_bars must be positive")
    if min_abs_delta < 0:
        raise ValueError("min_abs_delta must be non-negative")

    rows: list[dict[str, object]] = []
    for comparison in comparisons:
        if comparison.get("scope") not in READINESS_SCOPES:
            continue

        bars = int(comparison.get("bars", 0))
        delta = float(comparison.get("delta_vs_baseline", 0.0))
        status = _readiness_status(
            bars=bars,
            delta_vs_baseline=delta,
            min_bars=min_bars,
            min_abs_delta=min_abs_delta,
        )
        rows.append(
            {
                "horizon": int(comparison["horizon"]),
                "scope": str(comparison["scope"]),
                "condition": str(comparison["condition"]),
                "bars": bars,
                "mean_forward_return": float(
                    comparison.get("mean_forward_return", 0.0)
                ),
                "up_rate": float(comparison.get("up_rate", 0.0)),
                "delta_vs_baseline": delta,
                "readiness": status,
                "may_change_scoring": False,
                "may_change_ranking": False,
                "may_change_actionability": False,
                "may_activate_detector": False,
                "requires_separate_production_pr": True,
                "reason": _readiness_reason(status),
            }
        )
    return rows


def audit(path: Path, horizons: tuple[int, ...]) -> dict[str, object]:
    df = pd.read_csv(path)
    required = {
        "symbol",
        "bar_index",
        "close",
        "volume_ratio",
        "spread_ratio",
        "existing_events",
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = df.sort_values(["symbol", "bar_index"]).copy()
    for col in ("close", "volume_ratio", "spread_ratio"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close", "volume_ratio", "spread_ratio"])
    df = df[(df.volume_ratio > 0) & (df.spread_ratio > 0)]
    df["relationship"] = [
        classify(e, r) for e, r in zip(df.volume_ratio, df.spread_ratio)
    ]
    df["events"] = df.existing_events.map(events)

    rows = []
    for symbol, group in df.groupby("symbol", sort=False):
        group = group.reset_index(drop=True)
        close = group["close"]
        for i in range(len(group)):
            base = float(close.iloc[i])
            record = group.iloc[i]
            for horizon in horizons:
                j = i + horizon
                if j >= len(group) or base <= 0:
                    continue
                forward_return = float(close.iloc[j] / base - 1.0)
                rows.append(
                    {
                        "symbol": symbol,
                        "bar_index": int(record.bar_index),
                        "relationship": record.relationship,
                        "events": record.events,
                        "horizon": horizon,
                        "forward_return": forward_return,
                        "forward_up": forward_return > 0,
                    }
                )

    outcome = pd.DataFrame(rows, columns=OUTCOME_COLUMNS)
    comparisons = []
    for horizon in horizons:
        h = outcome[outcome.horizon == horizon]
        if h.empty:
            continue
        baseline = float(h.forward_return.mean())
        for relationship, g in h.groupby("relationship"):
            _append_comparison(
                comparisons,
                horizon=horizon,
                scope="relationship",
                condition=relationship,
                group=g,
                baseline=baseline,
            )
        for event in EVENTS:
            mask = h.events.map(lambda x, event=event: event in x)
            g = h[mask]
            if len(g):
                _append_comparison(
                    comparisons,
                    horizon=horizon,
                    scope="event",
                    condition=event,
                    group=g,
                    baseline=baseline,
                )
        for event in EFFORT_RESULT_EVENTS:
            mask = h.events.map(lambda x, event=event: event in x)
            g = h[mask]
            if len(g):
                _append_comparison(
                    comparisons,
                    horizon=horizon,
                    scope="effort_result_event",
                    condition=event,
                    group=g,
                    baseline=baseline,
                )
        for event in EVENTS:
            for relationship in RELATION:
                mask = h.events.map(lambda x, event=event: event in x) & (
                    h.relationship == relationship
                )
                g = h[mask]
                if len(g):
                    _append_comparison(
                        comparisons,
                        horizon=horizon,
                        scope="event_plus_relationship",
                        condition=f"{event}+{relationship}",
                        group=g,
                        baseline=baseline,
                    )
        for event in EFFORT_RESULT_EVENTS:
            for relationship in RELATION:
                mask = h.events.map(lambda x, event=event: event in x) & (
                    h.relationship == relationship
                )
                g = h[mask]
                if len(g):
                    _append_comparison(
                        comparisons,
                        horizon=horizon,
                        scope="effort_result_event_plus_relationship",
                        condition=f"{event}+{relationship}",
                        group=g,
                        baseline=baseline,
                    )

    readiness = decision_value_readiness(comparisons)
    return {
        "source": str(path),
        "rows": len(df),
        "outcome_rows": len(outcome),
        "horizons": list(horizons),
        "comparisons": comparisons,
        "readiness": readiness,
        "audit_only": True,
    }


def _append_comparison(
    comparisons: list[dict[str, object]],
    *,
    horizon: int,
    scope: str,
    condition: str,
    group: pd.DataFrame,
    baseline: float,
) -> None:
    mean_forward_return = float(group.forward_return.mean())
    comparisons.append(
        {
            "horizon": horizon,
            "scope": scope,
            "condition": condition,
            "bars": int(len(group)),
            "mean_forward_return": mean_forward_return,
            "up_rate": float(group.forward_up.mean()),
            "delta_vs_baseline": mean_forward_return - baseline,
        }
    )


def _readiness_status(
    *,
    bars: int,
    delta_vs_baseline: float,
    min_bars: int,
    min_abs_delta: float,
) -> str:
    if bars < min_bars:
        return READINESS_INSUFFICIENT_SAMPLE
    if abs(delta_vs_baseline) >= min_abs_delta:
        return READINESS_CANDIDATE
    return READINESS_OBSERVATION_ONLY


def _readiness_reason(status: str) -> str:
    if status == READINESS_INSUFFICIENT_SAMPLE:
        return "Keep as audit evidence only until the cohort has enough rows."
    if status == READINESS_CANDIDATE:
        return (
            "Candidate for calibration review only; scoring, ranking, "
            "actionability, and detector activation require a separate PR."
        )
    return (
        "Observed cohort does not clear the decision-value threshold for "
        "calibration review."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("historical_effort_result_validation.csv"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("effort_result_decision_value_audit.json"),
    )
    parser.add_argument("--horizons", nargs="+", type=int, default=[1, 2, 4])
    args = parser.parse_args()
    report = audit(args.input, tuple(args.horizons))
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Audited {report['outcome_rows']} point-in-time outcomes")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
