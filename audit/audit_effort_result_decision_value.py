"""Audit point-in-time Effort vs Result decision value against forward outcomes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

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

EVENTS = ("NO_DEMAND", "NO_SUPPLY", "STOPPING_VOLUME", "BUYING_CLIMAX", "SUPPLY_COMING_IN", "UPTHRUST")


def events(value: object) -> set[str]:
    if not isinstance(value, str) or not value.strip():
        return set()
    try:
        raw = json.loads(value)
    except json.JSONDecodeError:
        return set()
    out = set()
    for item in raw if isinstance(raw, list) else []:
        code = item if isinstance(item, str) else item.get("code") if isinstance(item, dict) else None
        if code:
            out.add(str(code).rsplit(".", 1)[-1].upper())
    return out


def classify(effort: float, result: float) -> str:
    for name, predicate in RELATION.items():
        if predicate(effort, result):
            return name
    return "unclassified"


def audit(path: Path, horizons: tuple[int, ...]) -> dict[str, object]:
    df = pd.read_csv(path)
    required = {"symbol", "bar_index", "close", "volume_ratio", "spread_ratio", "existing_events"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    df = df.sort_values(["symbol", "bar_index"]).copy()
    for col in ("close", "volume_ratio", "spread_ratio"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["close", "volume_ratio", "spread_ratio"])
    df = df[(df.volume_ratio > 0) & (df.spread_ratio > 0)]
    df["relationship"] = [classify(e, r) for e, r in zip(df.volume_ratio, df.spread_ratio)]
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
                rows.append({
                    "symbol": symbol,
                    "bar_index": int(record.bar_index),
                    "relationship": record.relationship,
                    "events": record.events,
                    "horizon": horizon,
                    "forward_return": forward_return,
                    "forward_up": forward_return > 0,
                })

    outcome = pd.DataFrame(rows)
    comparisons = []
    for horizon in horizons:
        h = outcome[outcome.horizon == horizon]
        baseline = h.forward_return.mean()
        for relationship, g in h.groupby("relationship"):
            comparisons.append({"horizon": horizon, "scope": "relationship", "condition": relationship, "bars": len(g), "mean_forward_return": g.forward_return.mean(), "up_rate": g.forward_up.mean(), "delta_vs_baseline": g.forward_return.mean() - baseline})
        for event in EVENTS:
            mask = h.events.map(lambda x: event in x)
            g = h[mask]
            if len(g):
                comparisons.append({"horizon": horizon, "scope": "event", "condition": event, "bars": len(g), "mean_forward_return": g.forward_return.mean(), "up_rate": g.forward_up.mean(), "delta_vs_baseline": g.forward_return.mean() - baseline})
        for event in EVENTS:
            for relationship in RELATION:
                mask = h.events.map(lambda x: event in x) & (h.relationship == relationship)
                g = h[mask]
                if len(g):
                    comparisons.append({"horizon": horizon, "scope": "event_plus_relationship", "condition": f"{event}+{relationship}", "bars": len(g), "mean_forward_return": g.forward_return.mean(), "up_rate": g.forward_up.mean(), "delta_vs_baseline": g.forward_return.mean() - baseline})

    return {"source": str(path), "rows": len(df), "outcome_rows": len(outcome), "horizons": list(horizons), "comparisons": comparisons}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("historical_effort_result_validation.csv"))
    parser.add_argument("--output", type=Path, default=Path("effort_result_decision_value_audit.json"))
    parser.add_argument("--horizons", nargs="+", type=int, default=[1, 2, 4])
    args = parser.parse_args()
    report = audit(args.input, tuple(args.horizons))
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Audited {report['outcome_rows']} point-in-time outcomes")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
