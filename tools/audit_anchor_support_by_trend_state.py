"""Trend-state segmented audit of PRIMARY + SUPPORTING evidence.

Investigation tool only. It does not alter production scoring.

For each PRIMARY + SUPPORTING combination, compare the pair against the
same PRIMARY event in the same trend_state with the supporting event absent.
Direction is canonical for known primary events, so stale CSV direction data
cannot invert favorable-return interpretation.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

RETURNS = ["return_1w", "return_2w", "return_4w", "return_8w", "mfe_8w", "mae_8w"]
HORIZONS = ["return_1w", "return_2w", "return_4w", "return_8w"]

PRIMARY = {"BUYING_CLIMAX", "UPTHRUST", "SPRING", "TEST", "SHAKEOUT", "SELLING_CLIMAX"}
SUPPORTING = {
    "SUPPLY_COMING_IN", "INCREASING_SUPPLY", "HIDDEN_SUPPLY", "SUPPLY_DRYING_UP",
    "SUPPLY_HIGH_VOLUME", "SUPPLY_WIDE_SPREAD", "SUPPLY_ABSORPTION", "STOPPING_VOLUME",
    "DEMAND_COMING_IN", "INCREASING_DEMAND", "HIDDEN_DEMAND", "DEMAND_DRYING_UP",
    "NO_SUPPLY", "NO_DEMAND",
}
DIRECTION = {
    "BUYING_CLIMAX": "BEARISH", "UPTHRUST": "BEARISH", "SELLING_CLIMAX": "BEARISH",
    "SPRING": "BULLISH", "TEST": "BULLISH", "SHAKEOUT": "BULLISH",
}


def find_col(df: pd.DataFrame, *names: str):
    cols = {str(c).strip().lower(): c for c in df.columns}
    return next((cols[n.lower()] for n in names if n.lower() in cols), None)


def prepare(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    mapping = {}
    aliases = {
        "event": ("event", "events"), "symbol": ("symbol",), "week": ("week", "date"),
        "bar_index": ("bar_index", "bar"), "trend_state": ("trend_state", "trendstate", "state"),
        "role": ("role",), "direction": ("direction",),
    }
    for target, names in aliases.items():
        column = find_col(df, *names)
        if column is not None:
            mapping[column] = target

    required = [name for name in ("event", "symbol", "week", "trend_state") if name not in mapping.values()]
    if required:
        raise ValueError(f"Missing required columns: {required}")

    df = df.rename(columns=mapping).copy()
    df["event"] = df["event"].astype(str).str.strip().str.upper()
    df["symbol"] = df["symbol"].astype(str).str.strip()
    df["trend_state"] = df["trend_state"].astype(str).str.strip().str.upper()
    df["week"] = pd.to_datetime(df["week"], errors="coerce").dt.normalize()

    if "bar_index" not in df:
        df["bar_index"] = pd.NA
    for column in RETURNS:
        if column in df:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.dropna(subset=["week", "trend_state"])


def build_observations(df: pd.DataFrame) -> pd.DataFrame:
    keys = (["symbol", "week", "bar_index", "trend_state"]
            if df["bar_index"].notna().any()
            else ["symbol", "week", "trend_state"])
    rows = []
    for key, group in df.groupby(keys, dropna=False, sort=False):
        events = sorted(set(group["event"].dropna()))
        if not events:
            continue
        kt = key if isinstance(key, tuple) else (key,)
        row = dict(zip(keys, kt))
        row["events"] = events
        for column in RETURNS:
            if column in group:
                values = group[column].dropna()
                row[column] = float(values.iloc[0]) if not values.empty else float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


def event_role(event: str, role_lookup: dict[str, str]) -> str:
    source = role_lookup.get(event)
    if source:
        return source
    if event in PRIMARY:
        return "PRIMARY"
    if event in SUPPORTING:
        return "SUPPORTING"
    return "OTHER"


def event_direction(event: str, direction_lookup: dict[str, str]) -> str:
    canonical = DIRECTION.get(event)
    if canonical is not None:
        return canonical
    source = direction_lookup.get(event)
    if source in {"BULLISH", "BEARISH"}:
        return source
    return "UNKNOWN"


def favorable_delta(direction: str, value: float) -> float:
    if pd.isna(value):
        return float("nan")
    if direction == "BULLISH":
        return float(value)
    if direction == "BEARISH":
        return -float(value)
    return float("nan")


def classify(cases: int, baseline_cases: int, favorable: list[float], min_cases: int) -> str:
    if cases < min_cases or baseline_cases < min_cases:
        return "LOW_SAMPLE"
    values = [value for value in favorable if pd.notna(value)]
    if not values:
        return "NO_BASELINE"
    positive = sum(value > 0 for value in values)
    negative = sum(value < 0 for value in values)
    if positive >= 3:
        return "CONFIRMING"
    if negative >= 3:
        return "CONTRADICTORY"
    return "MIXED"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="event_context_audit.csv")
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--min-cases", type=int, default=10)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    raw = prepare(args.input)
    observations = build_observations(raw)

    role_lookup: dict[str, str] = {}
    direction_lookup: dict[str, str] = {}
    if "role" in raw.columns:
        for event, group in raw.groupby("event"):
            values = group["role"].dropna().astype(str).str.upper().str.strip()
            if not values.empty:
                role_lookup[event] = values.mode().iloc[0]
    if "direction" in raw.columns:
        for event, group in raw.groupby("event"):
            values = group["direction"].dropna().astype(str).str.upper().str.strip()
            values = values[values.isin(["BULLISH", "BEARISH"])]
            if not values.empty:
                direction_lookup[event] = values.mode().iloc[0]

    role = lambda event: event_role(event, role_lookup)
    direction = lambda event: event_direction(event, direction_lookup)

    pair_rows: list[dict] = []
    summary_rows: list[dict] = []
    no_baseline_rows: list[dict] = []

    for _, observation in observations.iterrows():
        events = set(observation["events"])
        primaries = sorted(event for event in events if role(event) == "PRIMARY")
        supports = sorted(event for event in events if role(event) == "SUPPORTING")
        for anchor in primaries:
            for support in supports:
                pair_rows.append({
                    "anchor_event": anchor,
                    "supporting_event": support,
                    "trend_state": observation["trend_state"],
                    "symbol": observation["symbol"],
                    "week": observation["week"],
                    **{c: observation.get(c) for c in RETURNS},
                })

    pair_df = pd.DataFrame(pair_rows)

    if not pair_df.empty:
        for (anchor, support, trend_state), combo in pair_df.groupby(
            ["anchor_event", "supporting_event", "trend_state"], sort=True
        ):
            anchor_mask = observations["events"].apply(lambda values, event=anchor: event in set(values))
            support_absent_mask = observations["events"].apply(lambda values, event=support: event not in set(values))
            same_state_mask = observations["trend_state"].eq(trend_state)
            baseline = observations[anchor_mask & support_absent_mask & same_state_mask]

            cases = len(combo)
            baseline_cases = len(baseline)
            anchor_direction = direction(anchor)
            delta_avg = {
                f"delta_avg_{column}": (
                    combo[column].mean() - baseline[column].mean()
                    if not baseline.empty else float("nan")
                )
                for column in RETURNS
            }
            favorable = [favorable_delta(anchor_direction, delta_avg[f"delta_avg_{column}"]) for column in HORIZONS]

            row = {
                "anchor_event": anchor,
                "anchor_direction": anchor_direction,
                "supporting_event": support,
                "trend_state": trend_state,
                "cases": cases,
                "baseline_cases": baseline_cases,
                "classification": classify(cases, baseline_cases, favorable, args.min_cases),
                **delta_avg,
            }
            for column in HORIZONS:
                suffix = column.replace("return_", "")
                row[f"delta_favorable_{suffix}"] = favorable_delta(
                    anchor_direction, delta_avg[f"delta_avg_{column}"]
                )
            for column in RETURNS:
                row[f"combo_avg_{column}"] = combo[column].mean()
                row[f"baseline_avg_{column}"] = baseline[column].mean() if not baseline.empty else float("nan")
            summary_rows.append(row)

            if baseline_cases == 0:
                no_baseline_rows.append({
                    "anchor_event": anchor,
                    "anchor_direction": anchor_direction,
                    "supporting_event": support,
                    "trend_state": trend_state,
                    "combo_cases": cases,
                    "baseline_cases": 0,
                    "status": "UNAVOIDABLE_CO_OCCURRENCE_IN_TREND_STATE",
                })

    summary = pd.DataFrame(summary_rows)
    if not summary.empty:
        classification_order = {
            "CONFIRMING": 0, "CONTRADICTORY": 1, "MIXED": 2, "LOW_SAMPLE": 3, "NO_BASELINE": 4,
        }
        summary["_order"] = summary["classification"].map(classification_order).fillna(99)
        summary = summary.sort_values(
            ["_order", "cases", "anchor_event", "supporting_event", "trend_state"],
            ascending=[True, False, True, True, True],
        ).drop(columns="_order")

    summary_path = output_dir / "anchor_support_trend_state_summary.csv"
    pairs_path = output_dir / "anchor_support_trend_state_pairs.csv"
    no_baseline_path = output_dir / "anchor_support_trend_state_no_baseline.csv"
    summary.to_csv(summary_path, index=False)
    pair_df.to_csv(pairs_path, index=False)
    pd.DataFrame(no_baseline_rows).to_csv(no_baseline_path, index=False)

    print("=" * 100)
    print("DIRECTION-AWARE PRIMARY + SUPPORTING AUDIT BY TREND STATE")
    print("=" * 100)
    print(f"Input rows: {len(raw):,}")
    print(f"Unique observations: {len(observations):,}")
    print(f"PRIMARY + SUPPORTING pair rows: {len(pair_df):,}")
    print(f"Unavoidable co-occurrences: {len(no_baseline_rows):,}")
    print(f"Minimum cases: {args.min_cases}")
    print("\nSUMMARY")
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.3f}") if not summary.empty else "No PRIMARY + SUPPORTING combinations found.")
    print("\nOutputs:")
    print(summary_path)
    print(pairs_path)
    print(no_baseline_path)


if __name__ == "__main__":
    main()
