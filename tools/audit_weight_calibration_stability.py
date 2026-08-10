"""Weight-calibration stability audit for the historical VSA event audit.

Investigation tool only. It does not alter production scoring.

Tests whether weight-vs-outcome behavior is stable across chronological
periods within comparable VSA situations. The same event_context_audit.csv
used by the conditional-weight audit is expected as input.

No scipy dependency is required.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

HORIZONS = ["1w", "2w", "4w", "8w"]
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

BUCKETS = [
    (0.00, 1.00, "<1.00"),
    (1.00, 1.25, "1.00-<1.25"),
    (1.25, 1.50, "1.25-<1.50"),
    (1.50, 1.75, "1.50-<1.75"),
    (1.75, 2.01, ">=1.75"),
]
BUCKET_ORDER = {label: i for i, (_, _, label) in enumerate(BUCKETS)}


def prepare(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]

    required = ["event", "trend_state", "weight", "week", *[f"return_{h}" for h in HORIZONS]]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    for column in ["event", "trend_state"]:
        df[column] = df[column].astype(str).str.strip().str.upper()

    if "direction" in df.columns:
        df["direction"] = df["direction"].astype(str).str.strip().str.upper()
    else:
        df["direction"] = df["event"].map(DIRECTION)

    df["event_direction"] = df["event"].map(DIRECTION).fillna(df["direction"])
    df["event_direction"] = df["event_direction"].replace({"UNKNOWN": np.nan})
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
    df["week"] = pd.to_datetime(df["week"], errors="coerce")

    for horizon in HORIZONS:
        column = f"return_{horizon}"
        df[column] = pd.to_numeric(df[column], errors="coerce")
        df[f"favorable_return_{horizon}"] = np.where(
            df["event_direction"].eq("BEARISH"),
            -df[column],
            df[column],
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


def chronological_periods(df: pd.DataFrame, periods: int) -> pd.Series:
    """Return a chronological period label for every row.

    qcut is intentionally avoided because repeated weeks can create unstable
    boundaries. Rows are sorted by week and split into near-equal row counts.
    """
    if periods < 2:
        raise ValueError("periods must be at least 2")

    result = pd.Series(pd.NA, index=df.index, dtype="string")
    valid = df["week"].notna()
    ordered = df.loc[valid].sort_values("week").index.to_numpy()
    if len(ordered) == 0:
        return result

    chunks = np.array_split(ordered, periods)
    for i, chunk in enumerate(chunks, start=1):
        if len(chunk):
            result.loc[chunk] = f"P{i}"
    return result


def classify(values: list[float], tolerance: float = 1e-12) -> str:
    if len(values) < 2:
        return "INSUFFICIENT_SAMPLE"
    diffs = np.diff(values)
    non_decreasing = bool(np.all(diffs >= -tolerance))
    non_increasing = bool(np.all(diffs <= tolerance))
    if non_decreasing and non_increasing:
        return "FLAT"
    if non_decreasing:
        return "NON_DECREASING"
    if non_increasing:
        return "NON_INCREASING"
    return "NON_MONOTONIC"


def summarize_period_buckets(df: pd.DataFrame, min_cases: int) -> pd.DataFrame:
    group_columns = ["event", "event_direction", "trend_state", "period", "weight_bucket"]
    rows: list[dict[str, object]] = []

    grouped = df.dropna(subset=["weight", "period"]).groupby(
        group_columns, dropna=False, sort=False
    )
    for keys, group in grouped:
        row = dict(zip(group_columns, keys if isinstance(keys, tuple) else (keys,)))
        row["cases"] = len(group)
        row["qualifies"] = len(group) >= min_cases
        row["avg_weight"] = group["weight"].mean()
        for horizon in HORIZONS:
            row[f"avg_favorable_{horizon}"] = group[f"favorable_return_{horizon}"].mean()
            row[f"hit_rate_{horizon}"] = group[f"favorable_hit_{horizon}"].mean()
        rows.append(row)

    return pd.DataFrame(rows)


def period_stability(summary: pd.DataFrame, min_cases: int) -> pd.DataFrame:
    group_columns = ["event", "event_direction", "trend_state"]
    rows: list[dict[str, object]] = []

    for keys, group in summary.groupby(group_columns, dropna=False, sort=False):
        base = dict(zip(group_columns, keys if isinstance(keys, tuple) else (keys,)))
        qualifying = group[group["cases"] >= min_cases].copy()
        periods = sorted(qualifying["period"].dropna().unique())
        base["periods_with_qualifying_buckets"] = len(periods)
        base["qualifying_periods"] = ",".join(periods)
        base["qualifying_cases"] = int(qualifying["cases"].sum()) if not qualifying.empty else 0

        classifications: dict[str, list[str]] = {h: [] for h in HORIZONS}
        monotonic_periods = {h: 0 for h in HORIZONS}
        reverse_periods = {h: 0 for h in HORIZONS}
        nonmono_periods = {h: 0 for h in HORIZONS}

        for period in periods:
            pg = qualifying[qualifying["period"].eq(period)].copy()
            pg["bucket_order"] = pg["weight_bucket"].map(BUCKET_ORDER)
            pg = pg.sort_values("bucket_order")
            for horizon in HORIZONS:
                values = pg[f"avg_favorable_{horizon}"].dropna().tolist()
                cls = classify(values)
                classifications[horizon].append(cls)
                if cls == "NON_DECREASING":
                    monotonic_periods[horizon] += 1
                elif cls == "NON_INCREASING":
                    reverse_periods[horizon] += 1
                elif cls == "NON_MONOTONIC":
                    nonmono_periods[horizon] += 1

        for horizon in HORIZONS:
            classes = classifications[horizon]
            usable = [c for c in classes if c not in {"INSUFFICIENT_SAMPLE", "FLAT"}]
            base[f"{horizon}_period_classifications"] = ";".join(classes) if classes else ""
            base[f"{horizon}_monotonic_periods"] = monotonic_periods[horizon]
            base[f"{horizon}_reverse_periods"] = reverse_periods[horizon]
            base[f"{horizon}_nonmonotonic_periods"] = nonmono_periods[horizon]
            if len(usable) < 2:
                base[f"{horizon}_stability"] = "INSUFFICIENT"
            elif all(c == "NON_DECREASING" for c in usable):
                base[f"{horizon}_stability"] = "STABLE_INCREASING"
            elif all(c == "NON_INCREASING" for c in usable):
                base[f"{horizon}_stability"] = "STABLE_DECREASING"
            else:
                base[f"{horizon}_stability"] = "UNSTABLE"

        stable_labels = [base[f"{h}_stability"] for h in HORIZONS]
        if len(periods) < 2:
            base["overall_stability"] = "INSUFFICIENT_PERIODS"
        elif all(x == "STABLE_INCREASING" for x in stable_labels):
            base["overall_stability"] = "STABLE_INCREASING"
        elif all(x == "STABLE_DECREASING" for x in stable_labels):
            base["overall_stability"] = "STABLE_DECREASING"
        elif any(x == "UNSTABLE" for x in stable_labels):
            base["overall_stability"] = "UNSTABLE"
        else:
            base["overall_stability"] = "MIXED"

        rows.append(base)

    return pd.DataFrame(rows)


def adjacent_period_deltas(summary: pd.DataFrame, min_cases: int) -> pd.DataFrame:
    group_columns = ["event", "event_direction", "trend_state", "period"]
    rows: list[dict[str, object]] = []

    for keys, group in summary.groupby(group_columns, dropna=False, sort=False):
        base = dict(zip(group_columns, keys if isinstance(keys, tuple) else (keys,)))
        group = group[group["cases"] >= min_cases].copy()
        group["bucket_order"] = group["weight_bucket"].map(BUCKET_ORDER)
        group = group.sort_values("bucket_order")
        records = group.to_dict("records")
        for lower, higher in zip(records, records[1:]):
            row = {
                **base,
                "lower_bucket": lower["weight_bucket"],
                "higher_bucket": higher["weight_bucket"],
                "lower_cases": lower["cases"],
                "higher_cases": higher["cases"],
            }
            for horizon in HORIZONS:
                row[f"delta_favorable_{horizon}"] = (
                    higher[f"avg_favorable_{horizon}"] - lower[f"avg_favorable_{horizon}"]
                )
                row[f"delta_hit_rate_{horizon}"] = (
                    higher[f"hit_rate_{horizon}"] - lower[f"hit_rate_{horizon}"]
                )
            rows.append(row)
    return pd.DataFrame(rows)


def classify_recommendation(stability_row: pd.Series) -> str:
    values = [stability_row[f"{h}_stability"] for h in HORIZONS]
    increasing = sum(v == "STABLE_INCREASING" for v in values)
    decreasing = sum(v == "STABLE_DECREASING" for v in values)
    unstable = sum(v == "UNSTABLE" for v in values)

    if unstable >= 2:
        return "DO_NOT_CALIBRATE"
    if increasing >= 3 and unstable == 0:
        return "CONSIDER_RETAIN"
    if decreasing >= 3 and unstable == 0:
        return "CONSIDER_INVERT"
    if increasing + decreasing >= 3:
        return "WEAK_DIRECTIONAL_EVIDENCE"
    return "FLATTEN_OR_RETAIN"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="event_context_audit.csv")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--min-cases", type=int, default=10)
    parser.add_argument("--periods", type=int, default=3)
    args = parser.parse_args()

    if args.min_cases < 2:
        raise ValueError("min-cases must be at least 2")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = prepare(args.input)
    df["period"] = chronological_periods(df, args.periods)

    summary = summarize_period_buckets(df, args.min_cases)
    stability = period_stability(summary, args.min_cases)
    adjacent = adjacent_period_deltas(summary, args.min_cases)

    if not stability.empty:
        stability["calibration_recommendation"] = stability.apply(
            classify_recommendation, axis=1
        )

    outputs = {
        "weight_calibration_stability_buckets.csv": summary,
        "weight_calibration_stability_summary.csv": stability,
        "weight_calibration_stability_adjacent_deltas.csv": adjacent,
    }
    for name, frame in outputs.items():
        frame.to_csv(output_dir / name, index=False)

    print("=" * 110)
    print("WEIGHT CALIBRATION STABILITY AUDIT")
    print("=" * 110)
    print(f"Input rows: {len(df):,}")
    print(f"Rows with usable weight: {df['weight'].notna().sum():,}")
    print(f"Chronological periods: {args.periods}")
    print(f"Minimum cases per bucket: {args.min_cases}")
    print("\nSTABILITY SUMMARY")
    if stability.empty:
        print("No conditioning groups found.")
    else:
        columns = [
            "event", "event_direction", "trend_state", "periods_with_qualifying_buckets",
            "qualifying_cases", *[f"{h}_stability" for h in HORIZONS],
            "overall_stability", "calibration_recommendation",
        ]
        print(stability[columns].to_string(index=False))

    print("\nADJACENT-BUCKET PERIOD DELTAS")
    if adjacent.empty:
        print("No qualifying adjacent buckets.")
    else:
        columns = [
            "event", "event_direction", "trend_state", "period",
            "lower_bucket", "higher_bucket", "lower_cases", "higher_cases",
            *[f"delta_favorable_{h}" for h in HORIZONS],
            *[f"delta_hit_rate_{h}" for h in HORIZONS],
        ]
        print(adjacent[columns].to_string(index=False, float_format=lambda x: f"{x:.3f}"))

    print("\nOUTPUTS")
    for name in outputs:
        print(output_dir / name)


if __name__ == "__main__":
    main()
