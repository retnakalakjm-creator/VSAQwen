"""Weight-bucket effectiveness audit for the historical VSA event audit.

Investigation tool only. It does not alter production scoring.

The audit tests whether higher production weights correspond to better
forward outcomes. Favorable return is direction-aware: bullish events prefer
positive returns and bearish events prefer negative returns.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = ["return_1w", "return_2w", "return_4w", "return_8w"]
EXCURSIONS = ["mfe_8w", "mae_8w"]
REQUIRED = ["event", "direction", "trend_state", "weight", *HORIZONS, *EXCURSIONS]

BUCKETS = [
    (0.00, 1.00, "<1.00"),
    (1.00, 1.25, "1.00-<1.25"),
    (1.25, 1.50, "1.25-<1.50"),
    (1.50, 1.75, "1.50-<1.75"),
    (1.75, 2.01, ">=1.75"),
]

DIRECTION = {
    "BUYING_CLIMAX": "BEARISH", "UPTHRUST": "BEARISH", "SELLING_CLIMAX": "BEARISH",
    "SPRING": "BULLISH", "TEST": "BULLISH", "SHAKEOUT": "BULLISH",
    "SUPPLY_COMING_IN": "BEARISH", "INCREASING_SUPPLY": "BEARISH",
    "HIDDEN_SUPPLY": "BEARISH", "SUPPLY_DRYING_UP": "BULLISH",
    "NO_DEMAND": "BEARISH", "NO_SUPPLY": "BULLISH",
}


def prepare(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    for column in ["event", "direction", "trend_state"]:
        df[column] = df[column].astype(str).str.strip().str.upper()

    df["event_direction"] = df["event"].map(DIRECTION).fillna(df["direction"])
    df["event_direction"] = df["event_direction"].replace({"UNKNOWN": np.nan})

    df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
    for column in [*HORIZONS, *EXCURSIONS]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    for horizon in ["1w", "2w", "4w", "8w"]:
        df[f"favorable_return_{horizon}"] = np.where(
            df["event_direction"].eq("BEARISH"),
            -df[f"return_{horizon}"],
            df[f"return_{horizon}"],
        )

    df["weight_bucket"] = pd.cut(
        df["weight"],
        bins=[lo for lo, _, _ in BUCKETS] + [BUCKETS[-1][1]],
        labels=[label for _, _, label in BUCKETS],
        right=False,
        include_lowest=True,
    ).astype("string")
    return df


def summarize(df: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    rows = []
    for keys, group in df.groupby(group_columns, dropna=False, sort=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_columns, keys))
        row["cases"] = len(group)
        row["avg_weight"] = group["weight"].mean()
        row["median_weight"] = group["weight"].median()
        for horizon in ["1w", "2w", "4w", "8w"]:
            favorable = group[f"favorable_return_{horizon}"]
            row[f"avg_favorable_return_{horizon}"] = favorable.mean()
            row[f"median_favorable_return_{horizon}"] = favorable.median()
            row[f"favorable_hit_rate_{horizon}"] = (favorable > 0).mean()
        row["avg_mfe_8w"] = group["mfe_8w"].mean()
        row["median_mfe_8w"] = group["mfe_8w"].median()
        row["avg_mae_8w"] = group["mae_8w"].mean()
        row["median_mae_8w"] = group["mae_8w"].median()
        rows.append(row)
    return pd.DataFrame(rows)


def monotonicity(summary: pd.DataFrame, group_columns: list[str], min_cases: int) -> pd.DataFrame:
    rows = []
    group_key = [c for c in group_columns if c != "weight_bucket"]
    groups = [((), summary)] if not group_key else summary.groupby(group_key, dropna=False, sort=False)
    bucket_order = {label: i for i, (_, _, label) in enumerate(BUCKETS)}

    for keys, group in groups:
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_key, keys))
        group = group[group["cases"] >= min_cases].copy()
        group["bucket_order"] = group["weight_bucket"].map(bucket_order)
        group = group.sort_values("bucket_order")
        row["qualifying_buckets"] = len(group)

        for horizon in ["1w", "2w", "4w", "8w"]:
            values = group[f"avg_favorable_return_{horizon}"].dropna().to_numpy()
            if len(values) < 2:
                row[f"monotonicity_{horizon}"] = "INSUFFICIENT"
                continue
            diffs = np.diff(values)
            if np.all(diffs >= -1e-12):
                row[f"monotonicity_{horizon}"] = "NON_DECREASING"
            elif np.all(diffs <= 1e-12):
                row[f"monotonicity_{horizon}"] = "NON_INCREASING"
            else:
                row[f"monotonicity_{horizon}"] = "NON_MONOTONIC"
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="event_context_audit.csv")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--min-cases", type=int, default=10)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    df = prepare(args.input)

    overall = summarize(df, ["weight_bucket"])
    by_event = summarize(df, ["event", "event_direction", "weight_bucket"])
    by_event_trend = summarize(df, ["event", "event_direction", "trend_state", "weight_bucket"])

    overall_mono = monotonicity(overall, ["weight_bucket"], args.min_cases)
    event_mono = monotonicity(by_event, ["event", "event_direction", "weight_bucket"], args.min_cases)
    event_trend_mono = monotonicity(
        by_event_trend,
        ["event", "event_direction", "trend_state", "weight_bucket"],
        args.min_cases,
    )

    case_columns = [
        c for c in [
            "symbol", "bar_index", "week", "event", "event_direction", "direction",
            "trend_state", "weight", "weight_bucket", *HORIZONS, *EXCURSIONS,
            *[f"favorable_return_{h}" for h in ["1w", "2w", "4w", "8w"]],
        ] if c in df.columns
    ]

    outputs = {
        "weight_bucket_effectiveness_summary.csv": overall,
        "weight_bucket_effectiveness_by_event.csv": by_event,
        "weight_bucket_effectiveness_by_event_trend.csv": by_event_trend,
        "weight_bucket_monotonicity.csv": overall_mono,
        "weight_bucket_monotonicity_by_event.csv": event_mono,
        "weight_bucket_monotonicity_by_event_trend.csv": event_trend_mono,
        "weight_bucket_effectiveness_cases.csv": df[case_columns],
    }
    for name, frame in outputs.items():
        frame.to_csv(output_dir / name, index=False)

    print("=" * 110)
    print("WEIGHT-BUCKET EFFECTIVENESS AUDIT")
    print("=" * 110)
    print(f"Input rows: {len(df):,}")
    print(f"Rows with usable weight: {df['weight'].notna().sum():,}")
    print(f"Rows with known event direction: {df['event_direction'].notna().sum():,}")
    print(f"Minimum cases for monotonicity: {args.min_cases}")
    print("\nOVERALL WEIGHT-BUCKET SUMMARY")
    print(overall.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print("\nEVENT MONOTONICITY")
    print(event_mono.to_string(index=False) if not event_mono.empty else "No qualifying event groups.")
    print("\nEVENT + TREND-STATE MONOTONICITY")
    print(event_trend_mono.to_string(index=False) if not event_trend_mono.empty else "No qualifying event/trend groups.")
    print("\nOUTPUTS")
    for name in outputs:
        print(output_dir / name)


if __name__ == "__main__":
    main()
