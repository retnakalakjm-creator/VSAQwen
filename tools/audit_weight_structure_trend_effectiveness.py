"""Weight x structural-pattern x trend-state effectiveness audit.

Investigation tool only. It does not alter production scoring.

Builds campaign-level observations from the event-context audit, then asks
whether campaign weight behaves differently for the same structural event
pattern in different trend states.
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
    (1.00, 1.50, "1.00-<1.50"),
    (1.50, 2.00, "1.50-<2.00"),
    (2.00, 2.50, "2.00-<2.50"),
    (2.50, 3.00, "2.50-<3.00"),
    (3.00, np.inf, ">=3.00"),
]


def prepare(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    for column in ["event", "direction", "trend_state"]:
        df[column] = df[column].astype(str).str.strip().str.upper()
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
    for column in [*RETURN_COLUMNS, *EXCURSIONS]:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    if "campaign_id" not in df.columns:
        identity = [c for c in ["symbol", "week"] if c in df.columns]
        if len(identity) != 2:
            raise ValueError("Input must contain campaign_id or both symbol and week")
        if "bar_index" in df.columns:
            identity.append("bar_index")
        df["campaign_id"] = df[identity].astype(str).agg("|".join, axis=1)

    return df


def _direction(values: pd.Series) -> str:
    values = values.dropna().astype(str).str.upper()
    if values.empty:
        return "UNKNOWN"
    unique = set(values)
    if unique == {"BULLISH"}:
        return "BULLISH"
    if unique == {"BEARISH"}:
        return "BEARISH"
    return "MIXED"


def _single_value(group: pd.DataFrame, column: str) -> tuple[float, bool]:
    values = group[column].dropna()
    if values.empty:
        return float("nan"), False
    unique = values.unique()
    return float(unique[0]), len(unique) > 1


def _campaign_outcome(group: pd.DataFrame, horizon: str) -> tuple[float, bool]:
    return _single_value(group, f"return_{horizon}")


def build_campaigns(df: pd.DataFrame) -> pd.DataFrame:
    # One observation may contain the same event more than once. The event
    # pattern should list it once and the production weight should contribute
    # once, not once per duplicate evidence row.
    event_rows = df.drop_duplicates(["campaign_id", "event"], keep="first")

    rows: list[dict] = []
    for campaign_id, group in event_rows.groupby("campaign_id", sort=False):
        events = sorted(set(group["event"].dropna().astype(str)))
        states = sorted(set(group["trend_state"].dropna().astype(str)))
        row = {
            "campaign_id": campaign_id,
            "event_pattern": ",".join(events),
            "event_count": len(events),
            "trend_state": states[0] if len(states) == 1 else "MIXED",
            "campaign_direction": _direction(group["direction"]),
            "campaign_weight": group["weight"].sum(min_count=1),
        }

        for horizon in HORIZONS:
            value, conflict = _campaign_outcome(group, horizon)
            row[f"return_{horizon}"] = value
            row[f"return_{horizon}_conflict"] = conflict

        row["mfe_8w"], row["mfe_8w_conflict"] = _single_value(group, "mfe_8w")
        row["mae_8w"], row["mae_8w_conflict"] = _single_value(group, "mae_8w")
        rows.append(row)

    result = pd.DataFrame(rows)
    result["weight_bucket"] = pd.cut(
        result["campaign_weight"],
        bins=[lo for lo, _, _ in BUCKETS] + [BUCKETS[-1][1]],
        labels=[label for _, _, label in BUCKETS],
        right=False,
        include_lowest=True,
    ).astype("string")

    for horizon in HORIZONS:
        # Keep raw return columns untouched. Direction conversion happens
        # exactly once here.
        result[f"favorable_{horizon}"] = np.select(
            [
                result["campaign_direction"].eq("BEARISH"),
                result["campaign_direction"].eq("BULLISH"),
            ],
            [
                -result[f"return_{horizon}"],
                result[f"return_{horizon}"],
            ],
            default=np.nan,
        )
        # Missing outcomes remain missing; they are not counted as failures.
        result[f"hit_{horizon}"] = np.where(
            result[f"favorable_{horizon}"].notna(),
            (result[f"favorable_{horizon}"] > 0).astype(float),
            np.nan,
        )
    return result


def summarize(campaigns: pd.DataFrame) -> pd.DataFrame:
    groups = ["event_pattern", "event_count", "trend_state", "weight_bucket"]
    rows: list[dict] = []
    for keys, group in campaigns.groupby(groups, dropna=False, sort=False):
        row = dict(zip(groups, keys))
        row["cases"] = len(group)
        row["avg_campaign_weight"] = group["campaign_weight"].mean()
        row["median_campaign_weight"] = group["campaign_weight"].median()
        for horizon in HORIZONS:
            row[f"avg_return_{horizon}"] = group[f"return_{horizon}"].mean()
            row[f"median_return_{horizon}"] = group[f"return_{horizon}"].median()
            row[f"avg_favorable_{horizon}"] = group[f"favorable_{horizon}"].mean()
            row[f"hit_rate_{horizon}"] = group[f"hit_{horizon}"].mean()
        row["avg_mfe_8w"] = group["mfe_8w"].mean()
        row["median_mfe_8w"] = group["mfe_8w"].median()
        row["avg_mae_8w"] = group["mae_8w"].mean()
        row["median_mae_8w"] = group["mae_8w"].median()
        rows.append(row)
    return pd.DataFrame(rows)


def structure_trend_summary(campaigns: pd.DataFrame, min_cases: int) -> pd.DataFrame:
    """Baseline effectiveness by structural pattern and trend state only.

    This deliberately ignores weight buckets. It establishes the conditional
    baseline that later weight analysis must beat before weight can be treated
    as adding predictive information.
    """
    groups = ["event_pattern", "event_count", "trend_state"]
    rows: list[dict] = []

    for keys, group in campaigns.groupby(groups, dropna=False, sort=False):
        if len(group) < min_cases:
            continue

        row = dict(zip(groups, keys))
        row["cases"] = len(group)

        for horizon in HORIZONS:
            row[f"avg_return_{horizon}"] = group[f"return_{horizon}"].mean()
            row[f"median_return_{horizon}"] = group[f"return_{horizon}"].median()
            row[f"avg_favorable_{horizon}"] = group[f"favorable_{horizon}"].mean()
            row[f"hit_rate_{horizon}"] = group[f"hit_{horizon}"].mean()

        row["avg_mfe_8w"] = group["mfe_8w"].mean()
        row["median_mfe_8w"] = group["mfe_8w"].median()
        row["avg_mae_8w"] = group["mae_8w"].mean()
        row["median_mae_8w"] = group["mae_8w"].median()
        rows.append(row)

    return pd.DataFrame(rows)


def adjacent_deltas(summary: pd.DataFrame, min_cases: int) -> pd.DataFrame:
    order = {label: i for i, (_, _, label) in enumerate(BUCKETS)}
    groups = ["event_pattern", "event_count", "trend_state"]
    rows: list[dict] = []
    for keys, group in summary.groupby(groups, dropna=False, sort=False):
        group = group[group["cases"] >= min_cases].copy()
        if len(group) < 2:
            continue
        group["bucket_order"] = group["weight_bucket"].map(order)
        records = group.sort_values("bucket_order").to_dict("records")
        for lower, higher in zip(records, records[1:]):
            row = dict(zip(groups, keys))
            row.update({
                "lower_bucket": lower["weight_bucket"],
                "higher_bucket": higher["weight_bucket"],
                "lower_cases": lower["cases"],
                "higher_cases": higher["cases"],
            })
            for horizon in HORIZONS:
                row[f"delta_favorable_{horizon}"] = higher[f"avg_favorable_{horizon}"] - lower[f"avg_favorable_{horizon}"]
                row[f"delta_hit_rate_{horizon}"] = higher[f"hit_rate_{horizon}"] - lower[f"hit_rate_{horizon}"]
            rows.append(row)
    return pd.DataFrame(rows)


def pattern_summary(campaigns: pd.DataFrame, min_cases: int) -> pd.DataFrame:
    groups = ["event_pattern", "event_count", "trend_state"]
    rows: list[dict] = []
    for keys, group in campaigns.groupby(groups, dropna=False, sort=False):
        if len(group) < min_cases:
            continue
        row = dict(zip(groups, keys))
        row["cases"] = len(group)
        row["qualifying_weight_buckets"] = int(group["weight_bucket"].nunique(dropna=True))
        row["min_weight"] = group["campaign_weight"].min()
        row["max_weight"] = group["campaign_weight"].max()
        for horizon in HORIZONS:
            row[f"avg_favorable_{horizon}"] = group[f"favorable_{horizon}"].mean()
            row[f"hit_rate_{horizon}"] = group[f"hit_{horizon}"].mean()
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="event_context_audit.csv")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--min-cases", type=int, default=10)
    args = parser.parse_args()
    if args.min_cases <= 0:
        raise ValueError("--min-cases must be greater than zero")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw = prepare(args.input)
    campaigns = build_campaigns(raw)
    summary = summarize(campaigns)
    structure_trend = structure_trend_summary(campaigns, args.min_cases)
    adjacent = adjacent_deltas(summary, args.min_cases)
    patterns = pattern_summary(campaigns, args.min_cases)

    print(f"Input rows: {len(raw):,}")
    print(f"Unique campaigns: {campaigns['campaign_id'].nunique():,}")
    print(f"Structural patterns: {campaigns['event_pattern'].nunique():,}")
    print(f"Minimum cases per group: {args.min_cases}")
    conflict_columns = [
        c for c in campaigns.columns
        if c.endswith("_conflict") and campaigns[c].any()
    ]
    if conflict_columns:
        print(
            "WARNING: conflicting outcome values were found within campaigns: "
            + ", ".join(conflict_columns)
        )
    print()
    print("STRUCTURE x TREND BASELINE")
    print(
        structure_trend.to_string(index=False)
        if not structure_trend.empty
        else "No qualifying structure x trend groups."
    )
    print()
    print("WEIGHT x STRUCTURE x TREND SUMMARY")
    print(summary.to_string(index=False))
    print()
    print("ADJACENT-BUCKET EFFECTS")
    print(adjacent.to_string(index=False) if not adjacent.empty else "No qualifying adjacent buckets.")
    print()
    print("QUALIFYING STRUCTURAL PATTERNS")
    print(patterns.to_string(index=False) if not patterns.empty else "No qualifying structural patterns.")

    structure_trend.to_csv(output_dir / "structure_trend_summary.csv", index=False)
    summary.to_csv(output_dir / "weight_structure_trend_summary.csv", index=False)
    adjacent.to_csv(output_dir / "weight_structure_trend_adjacent_deltas.csv", index=False)
    patterns.to_csv(output_dir / "weight_structure_trend_patterns.csv", index=False)
    campaigns.to_csv(output_dir / "weight_structure_trend_campaigns.csv", index=False)


if __name__ == "__main__":
    main()
