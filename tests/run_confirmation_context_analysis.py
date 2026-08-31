from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_file")
    args = parser.parse_args()

    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in read_rows(Path(args.csv_file)):
        change = row["change"]
        for code in (code for code in row["confirmation_only_codes"].split(",") if code):
            groups[(code, change)].append(row)

    print("=== CONFIRMATION EVENT CONTEXT ANALYSIS ===")
    print(f"{'Code':<24}{'Change':<13}{'Cases':>7}{'MeanRet':>12}{'MeanMFE':>12}{'MeanMAE':>12}")
    for (code, change), rows in sorted(groups.items()):
        returns = [float(r["forward_return"]) for r in rows if r["forward_return"]]
        mfes = [float(r["mfe"]) for r in rows if r["mfe"]]
        maes = [float(r["mae"]) for r in rows if r["mae"]]
        mean = lambda values: sum(values) / len(values) if values else 0.0
        print(f"{code:<24}{change:<13}{len(rows):>7}{mean(returns):>12.4%}{mean(mfes):>12.4%}{mean(maes):>12.4%}")


if __name__ == "__main__":
    main()
