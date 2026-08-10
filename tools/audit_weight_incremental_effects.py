"""Weight incremental-effect audit conditioned on structure and trend.

Investigation tool only. It asks whether a weight bucket performs differently
from the other weight buckets inside the same structural-pattern x trend-state
conditioning group. Production scoring is untouched.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

HORIZONS = ["1w", "2w", "4w", "8w"]
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
    required = [
        "event",
        "direction",
        "trend_state",
        "weight",
        *[f"return_{h}" for h in HORIZONS],
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    for c in ["event", "direction", "trend_state"]:
        df[c] = df[c].astype(str).str.strip().str.upper()
    df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
    for c in [f"return_{h}" for h in HORIZONS] + ["mfe_8w", "mae_8w"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "campaign_id" not in df:
        identity = [c for c in ["symbol", "week", "bar_index"] if c in df.columns]
        if len(identity) < 2:
            raise ValueError("Input must contain campaign_id or enough identity columns")
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


def _single(group: pd.DataFrame, column: str) -> float:
    values = group[column].dropna()
    return float(values.iloc[0]) if not values.empty else float("nan")


def build_campaigns(df: pd.DataFrame) -> pd.DataFrame:
    event_rows = df.drop_duplicates(["campaign_id", "event"], keep="first")
    rows = []
    for campaign_id, group in event_rows.groupby("campaign_id", sort=False):
        events = sorted(set(group["event"].dropna()))
        states = sorted(set(group["trend_state"].dropna()))
        row = {
            "campaign_id": campaign_id,
            "event_pattern": ",".join(events),
            "event_count": len(events),
            "trend_state": states[0] if len(states) == 1 else "MIXED",
            "campaign_direction": _direction(group["direction"]),
            "campaign_weight": group["weight"].sum(min_count=1),
        }
        for h in HORIZONS:
            row[f"return_{h}"] = _single(group, f"return_{h}")
            row[f"favorable_{h}"] = (
                -row[f"return_{h}"]
                if row["campaign_direction"] == "BEARISH"
                else row[f"return_{h}"]
                if row["campaign_direction"] == "BULLISH"
                else float("nan")
            )
            row[f"hit_{h}"] = (
                float(row[f"favorable_{h}"] > 0)
                if pd.notna(row[f"favorable_{h}"])
                else float("nan")
            )
        row["mfe_8w"] = (
            _single(group, "mfe_8w") if "mfe_8w" in group else float("nan")
        )
        row["mae_8w"] = (
            _single(group, "mae_8w") if "mae_8w" in group else float("nan")
        )
        rows.append(row)

    result = pd.DataFrame(rows)
    result["weight_bucket"] = pd.cut(
        result["campaign_weight"],
        bins=[lo for lo, _, _ in BUCKETS] + [BUCKETS[-1][1]],
        labels=[label for _, _, label in BUCKETS],
        right=False,
        include_lowest=True,
    ).astype("string")
    return result


def weight_incremental_effects(
    campaigns: pd.DataFrame,
    min_cases: int,
) -> pd.DataFrame:
    """Compare each weight bucket with all other buckets in its structure/trend group.

    The leave-one-bucket-out baseline prevents the tested bucket from contributing
    to its own baseline. A result is emitted only when both the tested bucket and
    its comparison pool meet ``min_cases``.
    """
    groups = ["event_pattern", "event_count", "trend_state"]
    rows = []
    for keys, conditioned in campaigns.groupby(groups, dropna=False, sort=False):
        buckets = conditioned["weight_bucket"].dropna().unique().tolist()
        for bucket in buckets:
            tested = conditioned[conditioned["weight_bucket"] == bucket]
            baseline = conditioned[conditioned["weight_bucket"] != bucket]
            if len(tested) < min_cases or len(baseline) < min_cases:
                continue

            row = dict(zip(groups, keys))
            row.update(
                {
                    "weight_bucket": bucket,
                    "cases": len(tested),
                    "baseline_cases": len(baseline),
                    "avg_campaign_weight": tested["campaign_weight"].mean(),
                    "baseline_avg_campaign_weight": baseline["campaign_weight"].mean(),
                }
            )
            for h in HORIZONS:
                tested_fav = tested[f"favorable_{h}"].mean()
                baseline_fav = baseline[f"favorable_{h}"].mean()
                tested_hit = tested[f"hit_{h}"].mean()
                baseline_hit = baseline[f"hit_{h}"].mean()
                row[f"avg_favorable_{h}"] = tested_fav
                row[f"baseline_avg_favorable_{h}"] = baseline_fav
                row[f"delta_favorable_{h}"] = tested_fav - baseline_fav
                row[f"hit_rate_{h}"] = tested_hit
                row[f"baseline_hit_rate_{h}"] = baseline_hit
                row[f"delta_hit_rate_{h}"] = tested_hit - baseline_hit
            for c in ["mfe_8w", "mae_8w"]:
                row[f"avg_{c}"] = tested[c].mean()
                row[f"baseline_avg_{c}"] = baseline[c].mean()
                row[f"delta_avg_{c}"] = tested[c].mean() - baseline[c].mean()
            rows.append(row)

    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="weight_bucket_effectiveness_cases.csv")
    parser.add_argument("--output", default="weight_incremental_effects.csv")
    parser.add_argument("--min-cases", type=int, default=10)
    args = parser.parse_args()
    if args.min_cases <= 0:
        raise ValueError("--min-cases must be greater than zero")

    raw = prepare(args.input)
    campaigns = build_campaigns(raw)
    result = weight_incremental_effects(campaigns, args.min_cases)
    result.to_csv(args.output, index=False)

    print(f"Input rows: {len(raw):,}")
    print(f"Unique campaigns: {len(campaigns):,}")
    print(f"Qualifying incremental comparisons: {len(result):,}")
    print()
    print("WEIGHT INCREMENTAL EFFECTS — LEAVE-ONE-BUCKET-OUT")
    print(
        result.to_string(index=False)
        if not result.empty
        else "No qualifying comparisons."
    )


if __name__ == "__main__":
    main()
