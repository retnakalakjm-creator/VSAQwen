from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from confirmation_freshness_regime_analysis import analyze, summarize


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    args = parser.parse_args()

    rows = analyze(str(args.csv))
    summaries = summarize(rows)

    print("=== CONFIRMATION FRESHNESS / REGIME ANALYSIS ===")
    if not summaries:
        print("No matched cases found.")
        return

    print("Code                    Change         State         Cases MeanAge MeanRet   MeanMFE   MeanMAE")
    for row in summaries:
        mean_ret = "n/a" if row["mean_return"] is None else f"{row['mean_return']:+.4%}"
        mean_mfe = "n/a" if row["mean_mfe"] is None else f"{row['mean_mfe']:.4%}"
        mean_mae = "n/a" if row["mean_mae"] is None else f"{row['mean_mae']:.4%}"
        mean_age = "n/a" if row["mean_age"] is None else f"{row['mean_age']:.2f}"
        print(
            f"{row['code']:<24} {row['change']:<14} "
            f"{row['trend_state']:<12} {row['cases']:>5} {mean_age:>7} "
            f"{mean_ret:>9} {mean_mfe:>9} {mean_mae:>9}"
        )

    print("\n=== CASES ===")
    for row in rows:
        print(
            f"{row['symbol']:<14} bar={row['bar_index']:<5} "
            f"week={row['week']} change={row['change']:<11} "
            f"codes={row['confirmation_only_codes'] or '-':<24} "
            f"age={row['confirmation_age']} direction={row['trend_direction']} "
            f"state={row['trend_state']} score={row['professional_score']:.4f} "
            f"pressure={row['net_pressure']:.4f} return={row['forward_return']:+.4%} "
            f"mfe={row['mfe']:.4%} mae={row['mae']:.4%}"
        )


if __name__ == "__main__":
    main()
