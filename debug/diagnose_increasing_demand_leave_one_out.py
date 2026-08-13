from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_FILE = ROOT / "debug" / "output" / "increasing_demand_scoring_counterfactual.json"
WEIGHT = 0.85
POSITIVE = "POSITIVE_8_BAR"
NEGATIVE = "NEGATIVE_8_BAR"
FLAT = "FLAT_8_BAR"


def classify(row: dict) -> str:
    baseline = row["baseline_bias"]
    candidate = row["candidate_biases"][str(WEIGHT)]
    outcome = row["outcome"]
    if baseline == candidate:
        return "NO_CHANGE"
    if outcome == POSITIVE and candidate > baseline:
        return "BENEFICIAL"
    if outcome == NEGATIVE and candidate < baseline:
        return "BENEFICIAL"
    if outcome == FLAT:
        return "NEUTRAL"
    return "HARMFUL"


def main() -> None:
    payload = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    records = payload.get("event_records", [])
    if not records:
        raise RuntimeError("Point-in-time counterfactual records are required")

    symbols = sorted({row["symbol"] for row in records})
    print("INCREASING DEMAND LEAVE-ONE-SYMBOL-OUT SUMMARY")
    print({"candidate_weight": WEIGHT, "symbols": len(symbols), "events": len(records)})
    print("INCREASING DEMAND LEAVE-ONE-SYMBOL-OUT BY EXCLUSION")

    for excluded in symbols:
        rows = [row for row in records if row["symbol"] != excluded]
        counts = {"BENEFICIAL": 0, "HARMFUL": 0, "NEUTRAL": 0, "NO_CHANGE": 0}
        outcomes = {
            POSITIVE: {"beneficial": 0, "harmful": 0, "neutral": 0},
            NEGATIVE: {"beneficial": 0, "harmful": 0, "neutral": 0},
            FLAT: {"beneficial": 0, "harmful": 0, "neutral": 0},
        }
        transitions: dict[str, int] = {}
        for row in rows:
            result = classify(row)
            counts[result] += 1
            outcome = row["outcome"]
            if result != "NO_CHANGE":
                outcomes[outcome][result.lower()] += 1
            baseline = row["baseline_bias"]
            candidate = row["candidate_biases"][str(WEIGHT)]
            if baseline != candidate:
                key = f"{baseline}->{candidate}"
                transitions[key] = transitions.get(key, 0) + 1

        beneficial = counts["BENEFICIAL"]
        harmful = counts["HARMFUL"]
        print({
            "excluded_symbol": excluded,
            "events": len(rows),
            "beneficial_changes": beneficial,
            "harmful_changes": harmful,
            "neutral_changes": counts["NEUTRAL"],
            "net_benefit": beneficial - harmful,
            "benefit_harm_ratio": beneficial / harmful if harmful else None,
            "bias_transitions": transitions,
            "by_outcome": outcomes,
        })


if __name__ == "__main__":
    main()
