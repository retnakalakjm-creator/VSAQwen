from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "debug" / "output" / "increasing_demand_scoring_counterfactual.json"
OUTPUT_FILE = ROOT / "debug" / "output" / "increasing_demand_symbol_robustness.json"
WEIGHT = 0.85
POSITIVE = "POSITIVE_8_BAR"
NEGATIVE = "NEGATIVE_8_BAR"
FLAT = "FLAT_8_BAR"


def main() -> None:
    payload = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    records = payload.get("event_records", [])
    if not records:
        raise RuntimeError("Point-in-time counterfactual records are required")

    symbols = sorted({r["symbol"] for r in records})
    results = []
    for symbol in symbols:
        rows = [r for r in records if r["symbol"] == symbol]
        beneficial = harmful = neutral = 0
        by_outcome = {POSITIVE: 0, NEGATIVE: 0, FLAT: 0}
        for row in rows:
            outcome = row["outcome"]
            baseline = row["baseline_bias"]
            candidate = row["candidate_biases"][str(WEIGHT)]
            if baseline == candidate:
                continue
            if outcome == POSITIVE and candidate > baseline:
                beneficial += 1
                by_outcome[POSITIVE] += 1
            elif outcome == NEGATIVE and candidate < baseline:
                beneficial += 1
                by_outcome[NEGATIVE] += 1
            elif outcome == FLAT:
                neutral += 1
                by_outcome[FLAT] += 1
            else:
                harmful += 1

        results.append({
            "symbol": symbol,
            "events": len(rows),
            "beneficial_changes": beneficial,
            "harmful_changes": harmful,
            "neutral_changes": neutral,
            "net_benefit": beneficial - harmful,
            "benefit_harm_ratio": beneficial / harmful if harmful else None,
            "by_outcome": by_outcome,
        })

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps({"candidate_weight": WEIGHT, "symbols": results}, indent=2), encoding="utf-8")

    total_beneficial = sum(x["beneficial_changes"] for x in results)
    total_harmful = sum(x["harmful_changes"] for x in results)
    print("INCREASING DEMAND SYMBOL ROBUSTNESS SUMMARY")
    print({
        "candidate_weight": WEIGHT,
        "symbols": len(results),
        "events": len(records),
        "beneficial_changes": total_beneficial,
        "harmful_changes": total_harmful,
        "net_benefit": total_beneficial - total_harmful,
    })
    print("INCREASING DEMAND SYMBOL ROBUSTNESS BY SYMBOL")
    for item in results:
        print(item)
    print(f"DETAILS: {OUTPUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
