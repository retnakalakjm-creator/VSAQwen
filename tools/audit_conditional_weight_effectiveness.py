"""Conditional weight-effectiveness audit for the historical VSA event audit.

Investigation tool only. It does not alter production scoring.

Tests whether production weight is directionally useful *within comparable
VSA situations*, using event + trend_state as the conditioning group.
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
    rows = []
    group_columns = ["event", "event_direction", "trend_state", "weight_bucket"]
    for keys, group in df.groupby(group_columns, dropna=False, sort=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
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


def classify(values: list[float], tolerance: float = 1e-12) -> str:
    if len(values) < 2:
        return "INSUFFICIENT_SAMPLE"
    diffs = np.diff(values)
    non_decreasing = np.all(diffs >= -tolerance)
    non_increasing = np.all(diffs <= tolerance)
    if non_decreasing and non_increasing:
        return "FLAT"
    if non_decreasing:
        return "NON_DECREASING"
    if non_increasing:
        return "NON_INCREASING"
    return "NON_MONOTONIC"


def classify_overall(classes: list[str]) -> str:
    usable = [c for c in classes if c not in {"INSUFFICIENT_SAMPLE", "FLAT"}]
    if not usable:
        return "INSUFFICIENT_SAMPLE"
    if all(c == "NON_DECREASING" for c in usable):
        return "MONOTONIC"
    if all(c == "NON_INCREASING" for c in usable):
        return "REVERSE_MONOTONIC"
    return "NON_MONOTONIC"


def build_monotonicity(summary: pd.DataFrame, min_cases: int) -> pd.DataFrame:
    group_columns = ["event", "event_direction", "trend_state"]
    bucket_order = {label: i for i, (_, _, label) in enumerate(BUCKETS)}
    rows = []

    for keys, group in summary.groupby(group_columns, dropna=False, sort=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = dict(zip(group_columns, keys))

        group = group[group["cases"] >= min_cases].copy()
        group["bucket_order"] = group["weight_bucket"].map(bucket_order)
        group = group.sort_values("bucket_order")
        row["qualifying_buckets"] = len(group)
        row["qualifying_cases"] = int(group["cases"].sum())

        classifications = []
        for horizon in HORIZONS:
            values = group[f"avg_favorable_{horizon}"].dropna().tolist()
            result = classify(values)
            row[f"classification_{horizon}"] = result
            classifications.append(result)

        row["overall_classification"] = classify_overall(classifications)
        rows.append(row)

    return pd.DataFrame(rows)


def compare_adjacent_buckets(summary: pd.DataFrame, min_cases: int) -> pd.DataFrame:
    bucket_order = {label: i for i, (_, _, label) in enumerate(BUCKETS)}
    rows = []
    group_columns = ["event", "event_direction", "trend_state"]

    for keys, group in summary.groupby(group_columns, dropna=False, sort=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
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
                row[f"delta_avg_favorable_{horizon}"] = (
                    right[f"avg_favorable_{horizon}"] - left[f"avg_favorable_{horizon}"]
                )
                row[f"delta_hit_rate_{horizon}"] = (
                    right[f"favorable_hit_rate_{horizon}"] - left[f"favorable_hit_rate_{horizon}"]
                )
            rows.append(row)

    return pd.DataFrame(rows)


def weight_ranking_cases(df: pd.DataFrame, min_group_cases: int) -> pd.DataFrame:
    group_columns = ["event", "event_direction", "trend_state"]
    rows = []
    usable = df.dropna(subset=["weight", "event_direction"]).copy()

    for keys, group in usable.groupby(group_columns, dropna=False, sort=False):
        if len(group) < min_group_cases:
            continue
        for horizon in HORIZONS:
            metric = f"favorable_return_{horizon}"
            valid = group[["weight", metric]].dropna()
            if len(valid) < min_group_cases:
                continue

            # Spearman correlation = Pearson correlation of average ranks.
            # Using pandas rank() directly avoids pandas' scipy dependency.
            ranked = valid.rank(method="average")
            if ranked["weight"].nunique() < 2 or ranked[metric].nunique() < 2:
                corr = float("nan")
            else:
                corr = ranked["weight"].corr(
                    ranked[metric],
                    method="pearson",
                )

            rows.append({
                **dict(zip(group_columns, keys if isinstance(keys, tuple) else (keys,))),
                "horizon": horizon,
                "cases": len(valid),
                "spearman_weight_vs_favorable": corr,
            })

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
    mono = build_monotonicity(summary, args.min_cases)
    adjacent = compare_adjacent_buckets(summary, args.min_cases)
    ranking = weight_ranking_cases(df, args.min_cases)

    case_columns = [
        c for c in [
            "symbol", "bar_index", "week", "event", "event_direction", "direction",
            "trend_state", "weight", "weight_bucket", *RETURN_COLUMNS, *EXCURSIONS,
            *[f"favorable_return_{h}" for h in HORIZONS],
        ] if c in df.columns
    ]

    outputs = {
        "conditional_weight_effectiveness_buckets.csv": summary,
        "conditional_weight_monotonicity.csv": mono,
        "conditional_weight_adjacent_deltas.csv": adjacent,
        "conditional_weight_spearman.csv": ranking,
        "conditional_weight_effectiveness_cases.csv": df[case_columns],
    }
    for name, frame in outputs.items():
        frame.to_csv(output_dir / name, index=False)

    print("=" * 110)
    print("CONDITIONAL WEIGHT-EFFECTIVENESS AUDIT")
    print("=" * 110)
    print(f"Input rows: {len(df):,}")
    print(f"Rows with usable weight: {df['weight'].notna().sum():,}")
    print(f"Conditioning groups: {df.groupby(['event', 'event_direction', 'trend_state'], dropna=False).ngroups:,}")
    print(f"Minimum cases per bucket: {args.min_cases}")
    print("\nCONDITIONAL MONOTONICITY")
    print(mono.to_string(index=False) if not mono.empty else "No qualifying event/trend groups.")
    print("\nADJACENT-BUCKET DELTAS")
    print(adjacent.to_string(index=False, float_format=lambda x: f"{x:.3f}") if not adjacent.empty else "No qualifying adjacent buckets.")
    print("\nWITHIN-GROUP SPEARMAN RANK CORRELATION")
    print(ranking.to_string(index=False, float_format=lambda x: f"{x:.3f}") if not ranking.empty else "No qualifying groups.")
    print("\nOUTPUTS")
    for name in outputs:
        print(output_dir / name)


if __name__ == "__main__":
    main()
