from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = (0.25, 0.40, 0.60, 0.75, 0.85, 1.00)
INPUT_FILE = ROOT / "debug" / "output" / "increasing_demand_scoring_counterfactual.json"
OUTPUT_FILE = ROOT / "debug" / "output" / "increasing_demand_outcome_attribution.json"

POSITIVE = "POSITIVE_8_BAR"
NEGATIVE = "NEGATIVE_8_BAR"
FLAT = "FLAT_8_BAR"


def direction_level(bias: str) -> int:
    if bias == "BULLISH":
        return 1
    if bias == "BEARISH":
        return -1
    return 0


def classify_transition(baseline: str, candidate: str, outcome: str) -> str:
    if baseline == candidate:
        return "NO_CHANGE"
    base_level = direction_level(baseline)
    candidate_level = direction_level(candidate)
    if outcome == POSITIVE:
        return "BENEFICIAL" if candidate_level > base_level else "HARMFUL"
    if outcome == NEGATIVE:
        return "BENEFICIAL" if candidate_level < base_level else "HARMFUL"
    return "NEUTRAL"


def main() -> None:
    payload = json.loads(INPUT_FILE.read_text(encoding="utf-8"))
    records = payload.get("event_records", [])
    if not records:
        raise RuntimeError(
            "No point-in-time event_records found. Rerun diagnose_increasing_demand_scoring_counterfactual.py first."
        )

    results = []
    for weight in WEIGHTS:
        by_outcome = {
            POSITIVE: {"beneficial": 0, "harmful": 0, "neutral": 0, "no_change": 0},
            NEGATIVE: {"beneficial": 0, "harmful": 0, "neutral": 0, "no_change": 0},
            FLAT: {"beneficial": 0, "harmful": 0, "neutral": 0, "no_change": 0},
        }
        transitions: dict[str, int] = {}
        key = str(weight)

        for record in records:
            baseline = record["baseline_bias"]
            candidate = record["candidate_biases"][key]
            outcome = record["outcome"]
            classification = classify_transition(baseline, candidate, outcome)
            by_outcome[outcome][classification.lower()] += 1
            if baseline != candidate:
                transition = f"{baseline}->{candidate}"
                transitions[transition] = transitions.get(transition, 0) + 1

        beneficial = sum(v["beneficial"] for v in by_outcome.values())
        harmful = sum(v["harmful"] for v in by_outcome.values())
        results.append({
            "candidate_weight": weight,
            "events": len(records),
            "beneficial_changes": beneficial,
            "harmful_changes": harmful,
            "net_benefit": beneficial - harmful,
            "benefit_harm_ratio": beneficial / harmful if harmful else None,
            "bias_transitions": transitions,
            "by_outcome": by_outcome,
        })

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps({"weights": results}, indent=2), encoding="utf-8")

    print("INCREASING DEMAND OUTCOME ATTRIBUTION SUMMARY")
    print({"events": len(records), "weights": WEIGHTS})
    print("INCREASING DEMAND OUTCOME ATTRIBUTION BY WEIGHT")
    for item in results:
        print({
            "candidate_weight": item["candidate_weight"],
            "events": item["events"],
            "beneficial_changes": item["beneficial_changes"],
            "harmful_changes": item["harmful_changes"],
            "net_benefit": item["net_benefit"],
            "benefit_harm_ratio": item["benefit_harm_ratio"],
            "bias_transitions": item["bias_transitions"],
            "by_outcome": item["by_outcome"],
        })
    print(f"DETAILS: {OUTPUT_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
