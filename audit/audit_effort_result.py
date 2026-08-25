"""Audit the historical Effort vs Result validation dataset.

Observational only: no production scoring or engine invocation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS = {
    "symbol",
    "bar_index",
    "volume_ratio",
    "spread_ratio",
    "close_ratio",
    "direction",
    "trend_direction",
    "trend_state",
    "existing_events",
}

RELATION_BINS = (
    ("high_effort_low_result", lambda e, r: e >= 1.5 and r < 1.0),
    ("high_effort_normal_result", lambda e, r: e >= 1.5 and 1.0 <= r < 1.5),
    ("high_effort_high_result", lambda e, r: e >= 1.5 and r >= 1.5),
    ("normal_effort_low_result", lambda e, r: 0.75 <= e < 1.5 and r < 1.0),
    ("normal_effort_high_result", lambda e, r: 0.75 <= e < 1.5 and r >= 1.5),
    ("low_effort_high_result", lambda e, r: e < 0.75 and r >= 1.5),
    ("low_effort_normal_result", lambda e, r: e < 0.75 and 1.0 <= r < 1.5),
    ("low_effort_low_result", lambda e, r: e < 0.75 and r < 1.0),
)

EVENT_CODES = (
    "NO_DEMAND",
    "NO_SUPPLY",
    "STOPPING_VOLUME",
    "BUYING_CLIMAX",
    "SUPPLY_COMING_IN",
    "UPTHRUST",
)


def _classify(effort: float, result: float) -> str:
    for name, predicate in RELATION_BINS:
        if predicate(effort, result):
            return name
    return "unclassified"


def _event_set(value: object) -> set[str]:
    if not isinstance(value, str) or not value:
        return set()
    try:
        items = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return set()
    return {str(item.get("code")) for item in items if isinstance(item, dict)}


def audit(path: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    df = pd.read_csv(path)
    missing = REQUIRED_COLUMNS.difference(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    numeric = ["volume_ratio", "spread_ratio", "close_ratio"]
    for column in numeric:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    valid = df.dropna(subset=numeric).copy()
    valid = valid[(valid["volume_ratio"] > 0) & (valid["spread_ratio"] > 0)]
    valid["relationship"] = [
        _classify(effort, result)
        for effort, result in zip(valid["volume_ratio"], valid["spread_ratio"])
    ]
    valid["effort_result_ratio"] = valid["volume_ratio"] / valid["spread_ratio"]
    valid["events"] = valid["existing_events"].map(_event_set)

    distribution = (
        valid["relationship"].value_counts()
        .rename_axis("relationship")
        .reset_index(name="bars")
    )
    distribution["percent"] = distribution["bars"] / max(len(valid), 1) * 100.0

    interactions: list[dict[str, object]] = []
    for relationship, group in valid.groupby("relationship", sort=False):
        counts = {event: 0 for event in EVENT_CODES}
        for events in group["events"]:
            for event in EVENT_CODES:
                if event in events:
                    counts[event] += 1
        for event, count in counts.items():
            if count:
                interactions.append(
                    {
                        "relationship": relationship,
                        "event": event,
                        "bars": count,
                        "relationship_bars": len(group),
                        "percent_with_event": count / len(group) * 100.0,
                    }
                )

    report = {
        "source": str(path),
        "rows": int(len(df)),
        "valid_rows": int(len(valid)),
        "symbols": int(valid["symbol"].nunique()),
        "effort_mean": float(valid["volume_ratio"].mean()),
        "effort_median": float(valid["volume_ratio"].median()),
        "result_mean": float(valid["spread_ratio"].mean()),
        "result_median": float(valid["spread_ratio"].median()),
        "distribution": distribution.to_dict(orient="records"),
        "event_interactions": interactions,
    }
    return valid, report


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
        default=Path("effort_result_historical_audit.json"),
    )
    args = parser.parse_args()

    _, report = audit(args.input)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Audited {report['valid_rows']} valid rows across {report['symbols']} symbols")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
