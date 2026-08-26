"""Summarize persistent Effort vs Result decision value at 2 and 4 bars."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

MIN_SAMPLE = 100


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("effort_result_decision_value_audit.json"))
    parser.add_argument("--output", type=Path, default=Path("effort_result_persistence_summary.json"))
    args = parser.parse_args()

    report = json.loads(args.input.read_text(encoding="utf-8"))
    rows = pd.DataFrame(report["comparisons"])
    rows = rows[(rows["horizon"].isin([2, 4])) & (rows["bars"] >= MIN_SAMPLE)]
    rows = rows[rows["scope"] == "event_plus_relationship"].copy()

    if rows.empty:
        raise ValueError("No event + relationship combinations meet the minimum sample size")

    rows["condition_key"] = rows["condition"].astype(str)
    pivot = rows.pivot_table(
        index="condition_key",
        columns="horizon",
        values=["bars", "mean_forward_return", "up_rate", "delta_vs_baseline"],
        aggfunc="first",
    )

    results = []
    for condition in pivot.index:
        try:
            r2 = rows[(rows.condition_key == condition) & (rows.horizon == 2)].iloc[0]
            r4 = rows[(rows.condition_key == condition) & (rows.horizon == 4)].iloc[0]
        except IndexError:
            continue
        persistent_sign = (r2.delta_vs_baseline > 0) == (r4.delta_vs_baseline > 0)
        results.append({
            "condition": condition,
            "bars_2": int(r2.bars),
            "delta_2": float(r2.delta_vs_baseline),
            "up_rate_2": float(r2.up_rate),
            "bars_4": int(r4.bars),
            "delta_4": float(r4.delta_vs_baseline),
            "up_rate_4": float(r4.up_rate),
            "persistent_direction": bool(persistent_sign),
        })

    results.sort(key=lambda x: abs(x["delta_2"]) + abs(x["delta_4"]), reverse=True)
    output = {
        "source": str(args.input),
        "minimum_sample": MIN_SAMPLE,
        "horizons": [2, 4],
        "qualifying_combinations": len(results),
        "persistent_combinations": sum(x["persistent_direction"] for x in results),
        "results": results,
    }
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"Qualifying combinations: {len(results)}")
    print(f"Persistent direction: {output['persistent_combinations']}")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
