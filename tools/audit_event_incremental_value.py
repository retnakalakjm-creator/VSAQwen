"""Audit incremental outcome value of multi-event combinations.

This audit answers a narrower question than audit_event_combinations.py:
when an event is present with another event, does the combination behave
better or worse than observations where the anchor event occurs alone?

It deliberately does NOT modify production weights. Results are diagnostic.

Input: event_context_audit.csv (project root by default)
Outputs:
    event_incremental_cases.csv
    event_incremental_summary.csv
    event_incremental_anchors.csv
"""
from __future__ import annotations

import argparse
from itertools import combinations
from pathlib import Path

import pandas as pd

RETURN_COLUMNS = [
    "return_1w", "return_2w", "return_4w", "return_8w", "mfe_8w", "mae_8w",
]
KEY_COLUMNS = ["symbol", "week", "bar_index"]


def find_col(df: pd.DataFrame, *names: str):
    lower = {str(c).strip().lower(): c for c in df.columns}
    for name in names:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def prepare(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]

    event = find_col(df, "event", "events")
    symbol = find_col(df, "symbol")
    week = find_col(df, "week", "date")
    bar = find_col(df, "bar_index", "bar")

    missing = [
        name for name, col in (
            ("event", event),
            ("symbol", symbol),
            ("week", week),
        ) if col is None
    ]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    rename = {event: "event", symbol: "symbol", week: "week"}
    if bar is not None:
        rename[bar] = "bar_index"

    df = df.rename(columns=rename).copy()
    df["event"] = df["event"].astype(str).str.strip().str.upper()
    df["symbol"] = df["symbol"].astype(str).str.strip()
    df["week"] = pd.to_datetime(df["week"], errors="coerce").dt.normalize()

    if "bar_index" not in df:
        df["bar_index"] = pd.NA

    for col in RETURN_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df.dropna(subset=["week"])


def build_observations(df: pd.DataFrame) -> pd.DataFrame:
    use_bar = df["bar_index"].notna().any()
    keys = ["symbol", "week", "bar_index"] if use_bar else ["symbol", "week"]

    rows: list[dict] = []
    for key, group in df.groupby(keys, dropna=False, sort=False):
        events = sorted(set(group["event"].dropna()))
        if not events:
            continue

        key_tuple = key if isinstance(key, tuple) else (key,)
        row = dict(zip(keys, key_tuple))
        row["events"] = events
        row["event_count"] = len(events)

        for col in RETURN_COLUMNS:
            if col not in group.columns:
                continue
            values = group[col].dropna().unique()
            row[col] = float(values[0]) if len(values) else float("nan")
            row[f"{col}_conflict"] = len(values) > 1

        rows.append(row)

    return pd.DataFrame(rows)


def median_mean(group: pd.DataFrame, col: str) -> tuple[float, float]:
    if col not in group.columns:
        return float("nan"), float("nan")
    return float(group[col].mean()), float(group[col].median())


def build_incremental_cases(obs: pd.DataFrame) -> pd.DataFrame:
    """Create one row per anchor/pair observation.

    For A+B, the anchor is A and the comparison population is A-only.
    The same pair produces two directional rows: A <- A+B and B <- A+B.
    This lets us see whether the added event helps the anchor or merely
    inherits the behavior of the other event.
    """
    singles = obs[obs["event_count"] == 1].copy()
    pairs = obs[obs["event_count"] == 2].copy()

    rows: list[dict] = []
    for _, pair in pairs.iterrows():
        events = pair["events"]
        if len(events) != 2:
            continue

        for anchor, added in combinations(events, 2):
            # combinations() gives one ordering; emit both directions.
            for anchor_event, added_event in (
                (anchor, added),
                (added, anchor),
            ):
                baseline = singles[
                    singles["events"].apply(
                        lambda x: len(x) == 1 and x[0] == anchor_event
                    )
                ]

                row = {
                    "anchor_event": anchor_event,
                    "added_event": added_event,
                    "combination": f"{anchor_event} + {added_event}",
                    "symbol": pair["symbol"],
                    "week": pair["week"],
                    "pair_cases": 1,
                    "anchor_only_cases": len(baseline),
                }

                for col in RETURN_COLUMNS:
                    pair_value = pair.get(col, float("nan"))
                    baseline_mean, baseline_median = median_mean(baseline, col)
                    row[f"pair_{col}"] = pair_value
                    row[f"anchor_only_avg_{col}"] = baseline_mean
                    row[f"anchor_only_median_{col}"] = baseline_median
                    row[f"delta_vs_anchor_only_avg_{col}"] = (
                        float(pair_value) - baseline_mean
                        if pd.notna(pair_value) and pd.notna(baseline_mean)
                        else float("nan")
                    )

                rows.append(row)

    return pd.DataFrame(rows)


def summarize(cases: pd.DataFrame) -> pd.DataFrame:
    if cases.empty:
        return cases

    rows: list[dict] = []
    for combination, group in cases.groupby("combination", sort=True):
        row = {
            "combination": combination,
            "anchor_event": group["anchor_event"].iloc[0],
            "added_event": group["added_event"].iloc[0],
            "cases": len(group),
            "anchor_only_cases": int(group["anchor_only_cases"].iloc[0]),
        }

        for col in RETURN_COLUMNS:
            delta = f"delta_vs_anchor_only_avg_{col}"
            pair_col = f"pair_{col}"
            base_col = f"anchor_only_avg_{col}"
            row[f"pair_avg_{col}"] = group[pair_col].mean()
            row[f"anchor_only_avg_{col}"] = group[base_col].iloc[0]
            row[f"delta_avg_{col}"] = group[delta].mean()

        # Simple diagnostic classification only. It is intentionally not a
        # production scoring rule and should not be used with tiny samples.
        d4 = row.get("delta_avg_return_4w", float("nan"))
        d8 = row.get("delta_avg_return_8w", float("nan"))
        if row["cases"] < 10:
            classification = "LOW_SAMPLE"
        elif pd.notna(d4) and pd.notna(d8) and d4 >= 1.0 and d8 >= 1.0:
            classification = "CONFIRMING"
        elif pd.notna(d4) and pd.notna(d8) and d4 <= -1.0 and d8 <= -1.0:
            classification = "CONTRADICTORY"
        else:
            classification = "REDUNDANT_OR_MIXED"
        row["classification"] = classification
        rows.append(row)

    return pd.DataFrame(rows).sort_values(
        ["classification", "cases"],
        ascending=[True, False],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="event_context_audit.csv")
    parser.add_argument("--output-dir", default=".")
    args = parser.parse_args()

    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    raw = pd.read_csv(args.input)
    df = prepare(args.input)
    obs = build_observations(df)
    cases = build_incremental_cases(obs)
    summary = summarize(cases)

    cases.to_csv(outdir / "event_incremental_cases.csv", index=False)
    summary.to_csv(outdir / "event_incremental_summary.csv", index=False)
    obs.to_csv(outdir / "event_incremental_observations.csv", index=False)

    print("=" * 82)
    print("EVENT INCREMENTAL-VALUE AUDIT")
    print("=" * 82)
    print(f"Input rows: {len(raw):,}")
    print(f"Unique observations: {len(obs):,}")
    print(f"Single-event observations: {(obs.event_count == 1).sum():,}")
    print(f"Pair observations: {(obs.event_count == 2).sum():,}")
    print(f"Triple observations excluded from pair analysis: {(obs.event_count == 3).sum():,}")
    print(f"Incremental pair rows: {len(cases):,}")

    print("\nINCREMENTAL VALUE SUMMARY")
    if summary.empty:
        print("No pair combinations available.")
    else:
        display_cols = [
            "combination", "cases", "anchor_only_cases", "classification",
            "delta_avg_return_1w", "delta_avg_return_2w",
            "delta_avg_return_4w", "delta_avg_return_8w",
            "delta_avg_mfe_8w", "delta_avg_mae_8w",
        ]
        print(summary[display_cols].to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        ))

    print("\nIMPORTANT")
    print("Classification is diagnostic only. Do not change production weights from it yet.")
    print("Use cases >= 10 as the minimum sample filter; inspect sample sizes before calibration.")

    print("\nOutputs:")
    for name in (
        "event_incremental_summary.csv",
        "event_incremental_cases.csv",
        "event_incremental_observations.csv",
    ):
        print(outdir / name)


if __name__ == "__main__":
    main()
