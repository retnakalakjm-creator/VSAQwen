"""Event-specific weight calibration audit for the historical VSA event audit.

Investigation tool only. It does not alter production scoring.

Evaluates production weight ordering *within comparable VSA situations*
(event + event direction + trend state). The audit compares weight buckets
using favorable returns, favorable hit rates, MFE and MAE, then produces a
conservative calibration recommendation:

- RETAIN: higher weights consistently correspond to better favorable outcomes.
- INVERT: higher weights consistently correspond to worse favorable outcomes.
- FLATTEN: evidence is mixed / non-monotonic.
- INSUFFICIENT_SAMPLE: not enough populated buckets to judge ordering.

No SciPy dependency is required.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = ["1w", "2w", "4w", "8w"]
RETURN_COLUMNS = [f"return_{h}" for h in HORIZONS]
EXCURSIONS = ["mfe_8w", "mae_8w"]
REQUIRED = ["event", "direction", "trend_state", "weight", *RETURN_COLUMNS, *EXCURSIONS]

BUCKETS = [
    (0.00, 1.00, "<1.00"),
    (1.00, 1.25, "1.00-<1.25"),
    (1.25, 1.50, "1.25-<1.50"),
    (1.50, 1.75, "1.50-<1.75"),
    (1.75, 2.01, ">=1.75"),
]

DIRECTION = {
    "BUYING_CLIMAX": "BEARISH",
    "UPTHRUST": "BEARISH",
    "SELLING_CLIMAX": "BEARISH",
    "SPRING": "BULLISH",
    "TEST": "BULLISH",
    "SHAKEOUT": "BULLISH",
    "SUPPLY_COMING_IN": "BEARISH",
    "INCREASING_SUPPLY": "BEARISH",
    "HIDDEN_SUPPLY": "BEARISH",
    "SUPPLY_DRYING_UP": "BULLISH",
    "NO_DEMAND": "BEARISH",
    "NO_SUPPLY": "BULLISH",
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

    for column in [*RETURN_COLUMNS, *EXCURSIONS]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    for horizon in HORIZONS:
        source = f"return_{horizon}"
        df[f"favorable_return_{horizon}"] = np.where(
            df["event_direction"].eq("BEARISH"),
            -df[source],
            df[source],
        )
        df[f"favorable_hit_{horizon}"] = (
            df[f"favorable_return_{horizon}"] > 0
        ).astype(float)

    df["weight_bucket"] = pd.cut(
        df["weight"],
        bins=[lo for lo, _, _ in BUCKETS] + [BUCKETS[-1][1]],
        labels=[label for _, _, label in BUCKETS],
        right=False,
        include_lowest=True,
    ).astype("string")

    return df


def summarize_buckets(df: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    group_columns = ["event", "event_direction", "trend_state", "weight_bucket"]

    for keys, group in df.groupby(group_columns, dropna=False, sort=False):
        keys = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(group_columns, keys))
        row["cases"] = len(group)
        row["avg_weight"] = group["weight"].mean()
        row["median_weight"] = group["weight"].median()

        for horizon in HORIZONS:
            row[f"avg_favorable_{horizon}"] = group[f"favorable_return_{horizon}"].mean()
            row[f"median_favorable_{horizon}"] = group[f"favorable_return_{horizon}"].median()
            row[f"favorable_hit_rate_{horizon}"] = group[f"favorable_hit_{horizon}"].mean()

        row["avg_mfe_8w"] = group["mfe_8w"].mean()
        row["median_mfe_8w"] = group["mfe_8w"].median()
        row["avg_mae_8w"] = group["mae_8w"].mean()
        row["median_mae_8w"] = group["mae_8w"].median()
        rows.append(row)

    return pd.DataFrame(rows)


def _direction_for(values: list[float], tolerance: float = 1e-12) -> str:
    if len(values) < 2:
        return "INSUFFICIENT_SAMPLE"
    diffs = np.diff(values)
    if np.all(diffs >= -tolerance) and np.all(diffs <= tolerance):
        return "FLAT"
    if np.all(diffs >= -tolerance):
        return "NON_DECREASING"
    if np.all(diffs <= tolerance):
        return "NON_INCREASING"
    return "NON_MONOTONIC"


def _recommend(directions: list[str]) -> str:
    usable = [d for d in directions if d not in {"INSUFFICIENT_SAMPLE", "FLAT"}]
    if not usable:
        return "INSUFFICIENT_SAMPLE"
    if all(d == "NON_DECREASING" for d in usable):
        return "RETAIN"
    if all(d == "NON_INCREASING" for d in usable):
        return "INVERT"
    return "FLATTEN"


def _evidence_strength(total_cases: int, qualifying_buckets: int) -> str:
    if qualifying_buckets < 2:
        return "INSUFFICIENT"
    if qualifying_buckets >= 3 and total_cases >= 50:
        return "STRONG"
    if qualifying_buckets >= 3 and total_cases >= 30:
        return "MODERATE"
    return "WEAK"


def build_calibration(summary: pd.DataFrame, min_cases: int) -> pd.DataFrame:
    group_columns = ["event", "event_direction", "trend_state"]
    bucket_order = {label: i for i, (_, _, label) in enumerate(BUCKETS)}
    rows: list[dict] = []

    for keys, group in summary.groupby(group_columns, dropna=False, sort=False):
        keys = keys if isinstance(keys, tuple) else (keys,)
        row = dict(zip(group_columns, keys))

        qualified = group[group["cases"] >= min_cases].copy()
        qualified["bucket_order"] = qualified["weight_bucket"].map(bucket_order)
        qualified = qualified.sort_values("bucket_order")

        row["qualifying_buckets"] = len(qualified)
        row["qualifying_cases"] = int(qualified["cases"].sum())
        row["evidence_strength"] = _evidence_strength(
            row["qualifying_cases"], row["qualifying_buckets"]
        )

        directions: list[str] = []
        for horizon in HORIZONS:
            values = qualified[f"avg_favorable_{horizon}"].dropna().tolist()
            direction = _direction_for(values)
            row[f"ordering_{horizon}"] = direction
            directions.append(direction)

        hit_directions: list[str] = []
        for horizon in HORIZONS:
            values = qualified[f"favorable_hit_rate_{horizon}"].dropna().tolist()
            direction = _direction_for(values)
            row[f"hit_ordering_{horizon}"] = direction
            hit_directions.append(direction)

        row["return_recommendation"] = _recommend(directions)
        row["hit_rate_recommendation"] = _recommend(hit_directions)

        # Conservative final action: require the two evidence streams to agree.
        if row["return_recommendation"] == row["hit_rate_recommendation"]:
            row["calibration_action"] = row["return_recommendation"]
        elif "INSUFFICIENT_SAMPLE" in {
            row["return_recommendation"], row["hit_rate_recommendation"]
        }:
            row["calibration_action"] = "INSUFFICIENT_SAMPLE"
        else:
            row["calibration_action"] = "FLATTEN"

        if not qualified.empty:
            row["lowest_bucket"] = qualified.iloc[0]["weight_bucket"]
            row["highest_bucket"] = qualified.iloc[-1]["weight_bucket"]
            row["lowest_bucket_cases"] = int(qualified.iloc[0]["cases"])
            row["highest_bucket_cases"] = int(qualified.iloc[-1]["cases"])
        else:
            row["lowest_bucket"] = np.nan
            row["highest_bucket"] = np.nan
            row["lowest_bucket_cases"] = 0
            row["highest_bucket_cases"] = 0

        rows.append(row)

    return pd.DataFrame(rows)


def build_adjacent(summary: pd.DataFrame, min_cases: int) -> pd.DataFrame:
    group_columns = ["event", "event_direction", "trend_state"]
    bucket_order = {label: i for i, (_, _, label) in enumerate(BUCKETS)}
    rows: list[dict] = []

    for keys, group in summary.groupby(group_columns, dropna=False, sort=False):
        keys = keys if isinstance(keys, tuple) else (keys,)
        base = dict(zip(group_columns, keys))
        group = group[group["cases"] >= min_cases].copy()
        group["bucket_order"] = group["weight_bucket"].map(bucket_order)
        group = group.sort_values("bucket_order")
        ordered = group.to_dict("records")

        for left, right in zip(ordered, ordered[1:]):
            row = {
                **base,
                "lower_bucket": left["weight_bucket"],
                "higher_bucket": right["weight_bucket"],
                "lower_cases": left["cases"],
                "higher_cases": right["cases"],
            }
            for horizon in HORIZONS:
                row[f"delta_favorable_{horizon}"] = (
                    right[f"avg_favorable_{horizon}"] - left[f"avg_favorable_{horizon}"]
                )
                row[f"delta_hit_rate_{horizon}"] = (
                    right[f"favorable_hit_rate_{horizon}"] - left[f"favorable_hit_rate_{horizon}"]
                )
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
    summary = summarize_buckets(df)
    calibration = build_calibration(summary, args.min_cases)
    adjacent = build_adjacent(summary, args.min_cases)

    outputs = {
        "event_specific_weight_calibration.csv": calibration,
        "event_specific_weight_calibration_adjacent.csv": adjacent,
        "event_specific_weight_calibration_buckets.csv": summary,
    }
    for name, frame in outputs.items():
        frame.to_csv(output_dir / name, index=False)

    print("=" * 110)
    print("EVENT-SPECIFIC WEIGHT CALIBRATION AUDIT")
    print("=" * 110)
    print(f"Input rows: {len(df):,}")
    print(f"Rows with usable weight: {df['weight'].notna().sum():,}")
    print(
        "Conditioning groups: "
        f"{df.groupby(['event', 'event_direction', 'trend_state'], dropna=False).ngroups:,}"
    )
    print(f"Minimum cases per bucket: {args.min_cases}")

    print("\nCALIBRATION SUMMARY")
    columns = [
        "event", "event_direction", "trend_state", "qualifying_buckets",
        "qualifying_cases", "evidence_strength", "ordering_1w", "ordering_2w",
        "ordering_4w", "ordering_8w", "return_recommendation",
        "hit_rate_recommendation", "calibration_action",
    ]
    available = [c for c in columns if c in calibration.columns]
    print(calibration[available].to_string(index=False) if not calibration.empty else "No groups found.")

    print("\nADJACENT-BUCKET EVIDENCE")
    print(
        adjacent.to_string(index=False, float_format=lambda x: f"{x:.3f}")
        if not adjacent.empty
        else "No qualifying adjacent buckets."
    )

    print("\nOUTPUTS")
    for name in outputs:
        print(output_dir / name)


if __name__ == "__main__":
    main()
