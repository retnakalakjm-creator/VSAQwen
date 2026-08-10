"""Audit single-event vs multi-event outcome behavior.

Reads event_context_audit.csv from the project root (or --input) and treats
all evidence codes on the same symbol/week/bar_index as one observation.
This prevents correlated evidence from being counted as independent cases.
"""
from __future__ import annotations

import argparse
from itertools import combinations
from pathlib import Path
import pandas as pd

RETURN_COLUMNS = ["return_1w", "return_2w", "return_4w", "return_8w", "mfe_8w", "mae_8w"]
CONTEXT_COLUMNS = ["trend_direction", "trend_state", "phase"]


def find_col(df, *names):
    lower = {str(c).strip().lower(): c for c in df.columns}
    return next((lower[n.lower()] for n in names if n.lower() in lower), None)


def prepare(path):
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    event = find_col(df, "event", "events")
    symbol = find_col(df, "symbol")
    week = find_col(df, "week", "date")
    bar = find_col(df, "bar_index", "bar")
    missing = [n for n, c in (("event", event), ("symbol", symbol), ("week", week)) if c is None]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    ren = {event: "event", symbol: "symbol", week: "week"}
    if bar:
        ren[bar] = "bar_index"
    df = df.rename(columns=ren).copy()
    df["event"] = df["event"].astype(str).str.strip().str.upper()
    df["symbol"] = df["symbol"].astype(str).str.strip()
    df["week"] = pd.to_datetime(df["week"], errors="coerce").dt.normalize()
    if "bar_index" not in df:
        df["bar_index"] = pd.NA
    for c in RETURN_COLUMNS:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in CONTEXT_COLUMNS:
        if c in df:
            df[c] = df[c].astype(str).str.strip().replace("nan", "UNKNOWN")
    return df.dropna(subset=["week"])


def build_observations(df):
    keys = ["symbol", "week", "bar_index"] if df["bar_index"].notna().any() else ["symbol", "week"]
    rows = []
    for key, g in df.groupby(keys, dropna=False, sort=False):
        events = sorted(set(g["event"].dropna()))
        if not events:
            continue
        key_tuple = key if isinstance(key, tuple) else (key,)
        row = dict(zip(keys, key_tuple))
        row["events"] = ",".join(events)
        row["event_count"] = len(events)
        row["event_family"] = "SINGLE" if len(events) == 1 else "PAIR" if len(events) == 2 else "TRIPLE" if len(events) == 3 else "MULTI"
        for c in RETURN_COLUMNS:
            if c in g:
                vals = g[c].dropna()
                row[c] = float(vals.iloc[0]) if not vals.empty else float("nan")
                row[f"{c}_conflict"] = len(vals.unique()) > 1
        for c in CONTEXT_COLUMNS:
            if c in g:
                vals = g[c].dropna()
                row[c] = vals.iloc[0] if not vals.empty else "UNKNOWN"
        rows.append(row)
    return pd.DataFrame(rows)


def summarize(df, group_col):
    out = []
    for label, g in df.groupby(group_col, sort=True):
        r = {group_col: label, "cases": len(g)}
        for c in RETURN_COLUMNS:
            if c in g:
                r[f"avg_{c}"] = g[c].mean()
                r[f"median_{c}"] = g[c].median()
        out.append(r)
    return pd.DataFrame(out)


def combos(obs, n):
    rows = []
    for _, r in obs.iterrows():
        events = r["events"].split(",")
        if len(events) != n:
            continue
        for combo in combinations(events, n):
            x = {"event_combination": " + ".join(combo), "symbol": r["symbol"], "week": r["week"]}
            if "bar_index" in r:
                x["bar_index"] = r["bar_index"]
            for c in RETURN_COLUMNS + CONTEXT_COLUMNS:
                if c in r:
                    x[c] = r[c]
            rows.append(x)
    return pd.DataFrame(rows)


def combo_summary(df):
    if df.empty:
        return df
    rows = []
    for combo, g in df.groupby("event_combination", sort=True):
        r = {"event_combination": combo, "cases": len(g)}
        for c in RETURN_COLUMNS:
            if c in g:
                r[f"avg_{c}"] = g[c].mean()
                r[f"median_{c}"] = g[c].median()
        rows.append(r)
    return pd.DataFrame(rows).sort_values("cases", ascending=False)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", default="event_context_audit.csv")
    p.add_argument("--output-dir", default=".")
    a = p.parse_args()
    outdir = Path(a.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    raw = pd.read_csv(a.input)
    df = prepare(a.input)
    obs = build_observations(df)
    if obs.empty:
        raise ValueError("No valid observations created")
    obs.to_csv(outdir / "event_combination_cases.csv", index=False)
    fam = summarize(obs, "event_family")
    fam.to_csv(outdir / "event_combination_summary.csv", index=False)
    pair = combos(obs, 2)
    triple = combos(obs, 3)
    pair.to_csv(outdir / "event_combination_pairs.csv", index=False)
    triple.to_csv(outdir / "event_combination_triples.csv", index=False)
    ps = combo_summary(pair)
    ts = combo_summary(triple)
    print("=" * 78)
    print("EVENT COMBINATION / OUTCOME AUDIT")
    print("=" * 78)
    print(f"Input rows: {len(raw):,}")
    print(f"Unique observations: {len(obs):,}")
    print(f"Single-event observations: {(obs.event_count == 1).sum():,}")
    print(f"Pair observations: {(obs.event_count == 2).sum():,}")
    print(f"Triple observations: {(obs.event_count == 3).sum():,}")
    print(f"4+ event observations: {(obs.event_count >= 4).sum():,}")
    print("\nEVENT FAMILY SUMMARY")
    print(fam.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
    print("\nPAIR OUTCOME SUMMARY")
    print(ps.to_string(index=False, float_format=lambda x: f"{x:.3f}") if not ps.empty else "None")
    print("\nTRIPLE OUTCOME SUMMARY")
    print(ts.to_string(index=False, float_format=lambda x: f"{x:.3f}") if not ts.empty else "None")
    conflicts = [c for c in RETURN_COLUMNS if f"{c}_conflict" in obs and obs[f"{c}_conflict"].any()]
    if conflicts:
        print("\nWARNING: conflicting outcome values within observations:", ", ".join(conflicts))
    print("\nOutputs:")
    for name in ("event_combination_summary.csv", "event_combination_cases.csv", "event_combination_pairs.csv", "event_combination_triples.csv"):
        print(outdir / name)


if __name__ == "__main__":
    main()
