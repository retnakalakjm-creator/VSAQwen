"""Direction-aware audit of PRIMARY + SUPPORTING evidence.

This is an investigation tool only. It does not alter production scoring.
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
    "SUPPLY_HIGH_VOLUME", "SUPPLY_WIDE_SPREAD", "SUPPLY_ABSORPTION",
    "STOPPING_VOLUME", "DEMAND_COMING_IN", "INCREASING_DEMAND", "HIDDEN_DEMAND",
    "DEMAND_DRYING_UP", "NO_SUPPLY", "NO_DEMAND",
}
DIRECTION = {
    "BUYING_CLIMAX": "BEARISH", "UPTHRUST": "BEARISH", "SELLING_CLIMAX": "BEARISH",
    "SPRING": "BULLISH", "TEST": "BULLISH", "SHAKEOUT": "BULLISH",
}


def find_col(df, *names):
    cols = {str(c).strip().lower(): c for c in df.columns}
    return next((cols[n.lower()] for n in names if n.lower() in cols), None)


def prepare(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    mapping = {}
    for target, names in {
        "event": ("event", "events"), "symbol": ("symbol",), "week": ("week", "date"),
        "bar_index": ("bar_index", "bar"), "role": ("role",), "direction": ("direction",),
    }.items():
        c = find_col(df, *names)
        if c is not None:
            mapping[c] = target
    required = [k for k in ("event", "symbol", "week") if k not in mapping.values()]
    if required:
        raise ValueError(f"Missing required columns: {required}")
    df = df.rename(columns=mapping).copy()
    df["event"] = df["event"].astype(str).str.strip().str.upper()
    df["symbol"] = df["symbol"].astype(str).str.strip()
    df["week"] = pd.to_datetime(df["week"], errors="coerce").dt.normalize()
    if "bar_index" not in df:
        df["bar_index"] = pd.NA
    for c in RETURNS:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.dropna(subset=["week"])


def build_observations(df):
    keys = ["symbol", "week", "bar_index"] if df["bar_index"].notna().any() else ["symbol", "week"]
    rows = []
    for key, g in df.groupby(keys, dropna=False, sort=False):
        events = sorted(set(g["event"].dropna()))
        if not events:
            continue
        kt = key if isinstance(key, tuple) else (key,)
        row = dict(zip(keys, kt))
        row["events"] = events
        for c in RETURNS:
            if c in g:
                vals = g[c].dropna()
                row[c] = float(vals.iloc[0]) if not vals.empty else float("nan")
        rows.append(row)
    return pd.DataFrame(rows)


def event_role(event, source_role=None):
    if source_role:
        value = str(source_role).strip().upper()
        if value:
            return value
    return "PRIMARY" if event in PRIMARY else "SUPPORTING" if event in SUPPORTING else "OTHER"


def event_direction(event, source_direction=None):
    # Canonical production direction takes precedence for known events.
    # Do not allow a stale/incorrect direction column in the audit CSV to
    # override the event's defined semantic direction.
    canonical = DIRECTION.get(event)
    if canonical is not None:
        return canonical

    # Only use the source column as a fallback for events not explicitly
    # defined in the canonical audit mapping.
    if source_direction:
        value = str(source_direction).strip().upper()
        if value in {"BULLISH", "BEARISH"}:
            return value

    return "UNKNOWN"


def favorable_delta(anchor_direction, value):
    if pd.isna(value):
        return float("nan")
    # For bullish anchors, positive returns are favorable.
    # For bearish anchors, negative returns are favorable.
    return float(value) if anchor_direction == "BULLISH" else -float(value) if anchor_direction == "BEARISH" else float("nan")


def classify(cases, baseline_cases, favorable):
    if cases < 10 or baseline_cases < 10:
        return "LOW_SAMPLE"
    vals = [v for v in favorable if pd.notna(v)]
    if not vals:
        return "NO_BASELINE"
    first4 = vals[:4]
    positive = sum(v > 0 for v in first4)
    negative = sum(v < 0 for v in first4)
    if positive >= 3:
        return "CONFIRMING"
    if negative >= 3:
        return "CONTRADICTORY"
    return "MIXED"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="event_context_audit.csv")
    p.add_argument("--output-dir", default=".")
    p.add_argument("--min-cases", type=int, default=10)
    a = p.parse_args()
    out = Path(a.output_dir)
    out.mkdir(parents=True, exist_ok=True)

    raw = prepare(a.input)
    obs = build_observations(raw)

    role_lookup = {}
    direction_lookup = {}
    if "role" in raw.columns:
        for event, g in raw.groupby("event"):
            vals = g["role"].dropna().astype(str).str.upper().str.strip()
            if not vals.empty:
                role_lookup[event] = vals.mode().iloc[0]
    if "direction" in raw.columns:
        for event, g in raw.groupby("event"):
            vals = g["direction"].dropna().astype(str).str.upper().str.strip()
            vals = vals[vals.isin(["BULLISH", "BEARISH"])]
            if not vals.empty:
                direction_lookup[event] = vals.mode().iloc[0]

    def er(e): return event_role(e, role_lookup.get(e))
    def ed(e): return event_direction(e, direction_lookup.get(e))

    pair_rows, coprimary_rows, rows, no_baseline_rows = [], [], [], []
    for _, r in obs.iterrows():
        events = set(r["events"])
        primaries = sorted(e for e in events if er(e) == "PRIMARY")
        supports = sorted(e for e in events if er(e) == "SUPPORTING")
        for i, first in enumerate(primaries):
            for second in primaries[i + 1:]:
                coprimary_rows.append({"event_1": first, "event_2": second, "symbol": r["symbol"], "week": r["week"], **{c: r.get(c) for c in RETURNS}})
        for anchor in primaries:
            for support in supports:
                pair_rows.append({"anchor_event": anchor, "supporting_event": support, "symbol": r["symbol"], "week": r["week"], **{c: r.get(c) for c in RETURNS}})

    pair_df = pd.DataFrame(pair_rows)
    coprimary_df = pd.DataFrame(coprimary_rows)

    if not pair_df.empty:
        for (anchor, support), combo in pair_df.groupby(["anchor_event", "supporting_event"], sort=True):
            mask_anchor = obs["events"].apply(lambda x, e=anchor: e in set(x))
            mask_without = obs["events"].apply(lambda x, e=support: e not in set(x))
            baseline = obs[mask_anchor & mask_without]
            baseline_cases = len(baseline)
            cases = len(combo)
            direction = ed(anchor)
            raw_deltas = {f"delta_avg_{c}": (combo[c].mean() - baseline[c].mean()) if not baseline.empty else float("nan") for c in RETURNS}
            favorable = [favorable_delta(direction, raw_deltas[f"delta_avg_{c}"]) for c in HORIZONS]
            row = {
                "anchor_event": anchor, "anchor_direction": direction, "supporting_event": support,
                "cases": cases, "baseline_cases": baseline_cases,
                "classification": classify(cases, baseline_cases, favorable),
                **raw_deltas,
            }
            for c in HORIZONS:
                row[f"delta_favorable_{c.replace('return_', '')}"] = favorable_delta(direction, raw_deltas[f"delta_avg_{c}"])
            for c in RETURNS:
                row[f"combo_avg_{c}"] = combo[c].mean()
                row[f"baseline_avg_{c}"] = baseline[c].mean() if not baseline.empty else float("nan")
            rows.append(row)
            if baseline_cases == 0:
                no_baseline_rows.append({"anchor_event": anchor, "supporting_event": support, "combo_cases": cases, "anchor_without_support_cases": 0, "status": "UNAVOIDABLE_CO_OCCURRENCE"})

    summary = pd.DataFrame(rows)
    if not summary.empty:
        summary = summary.sort_values(["classification", "cases"], ascending=[True, False])
    summary.to_csv(out / "anchor_incremental_summary.csv", index=False)
    pair_df.to_csv(out / "anchor_incremental_pairs.csv", index=False)
    coprimary_df.to_csv(out / "anchor_coprimary_pairs.csv", index=False)
    pd.DataFrame(no_baseline_rows).to_csv(out / "anchor_unavoidable_cooccurrence.csv", index=False)

    print("=" * 90)
    print("DIRECTION-AWARE PRIMARY ANCHOR / SUPPORTING-EVIDENCE AUDIT")
    print("=" * 90)
    print(f"Input rows: {len(raw):,}")
    print(f"Unique observations: {len(obs):,}")
    print(f"PRIMARY + SUPPORTING pair rows: {len(pair_df):,}")
    print(f"Co-primary pair rows: {len(coprimary_df):,}")
    print(f"Unavoidable co-occurrences: {len(no_baseline_rows):,}")
    print("\nSUMMARY")
    print(summary.to_string(index=False, float_format=lambda x: f"{x:.3f}") if not summary.empty else "No PRIMARY + SUPPORTING combinations found.")
    print("\nOutputs:")
    for name in ("anchor_incremental_summary.csv", "anchor_incremental_pairs.csv", "anchor_coprimary_pairs.csv", "anchor_unavoidable_cooccurrence.csv"):
        print(out / name)


if __name__ == "__main__":
    main()
