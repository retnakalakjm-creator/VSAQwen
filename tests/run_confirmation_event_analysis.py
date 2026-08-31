from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from confirmation_event_analysis import analyze_file, render


def main() -> None:
    parser = argparse.ArgumentParser(description="Group changed-actionability outcomes by confirmation-only VSA event.")
    parser.add_argument("csv_path", nargs="?", default="confirmation_outcome_changed_cases.csv")
    args = parser.parse_args()

    path = Path(args.csv_path)
    if not path.exists():
        raise SystemExit(f"CSV not found: {path}")

    results = analyze_file(path)
    if not results:
        raise SystemExit("No confirmation-only changed cases found.")

    print(render(results))
    print(f"\nSource: {path.resolve()}")


if __name__ == "__main__":
    main()
