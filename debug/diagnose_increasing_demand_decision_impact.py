from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evidence.aggregator import EvidenceAggregator
from models import EvidenceCode

SOURCE = ROOT / "debug" / "diagnose_increasing_demand_scoring_counterfactual.py"
WEIGHTS = (0.25, 0.40, 0.60, 0.75, 0.85, 1.00)
OUTPUT = ROOT / "debug" / "output" / "increasing_demand_decision_impact.json"

# Reuse the validated 902-event replay instead of downloading/replaying data again.
# The source diagnostic stores the complete point-in-time evidence records in its
# JSON output only after execution; this wrapper intentionally reads that artifact.

def main() -> None:
    source_output = ROOT / "debug" / "output" / "increasing_demand_scoring_counterfactual.json"
    if not source_output.exists():
        raise RuntimeError("Run diagnose_increasing_demand_scoring_counterfactual.py first")

    payload = json.loads(source_output.read_text(encoding="utf-8"))
    impacts = []
    for item in payload.get("weight_impacts", []):
        weight = float(item["candidate_weight"])
        impacts.append({
            "candidate_weight": weight,
            "events": item.get("events", 0),
            "decision_changes": sum(item.get("bias_changes", {}).values()),
            "bias_changes": item.get("bias_changes", {}),
            "note": "Outcome-level decision attribution requires the point-in-time baseline/counterfactual records; this summary reports validated bias transitions only.",
        })

    result = {
        "symbols_requested": payload.get("symbols_requested", 0),
        "symbols_with_events": payload.get("symbols_with_events", 0),
        "events": payload.get("events", 0),
        "outcomes": payload.get("outcomes", {}),
        "candidate_weights": WEIGHTS,
        "failures": payload.get("failures", []),
        "weight_impacts": impacts,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print("INCREASING DEMAND DECISION IMPACT SUMMARY")
    print({
        "symbols_requested": result["symbols_requested"],
        "symbols_with_events": result["symbols_with_events"],
        "events": result["events"],
        "outcomes": result["outcomes"],
        "candidate_weights": WEIGHTS,
        "failures": len(result["failures"]),
    })
    print("INCREASING DEMAND DECISION IMPACT BY WEIGHT")
    for item in impacts:
        print(item)


if __name__ == "__main__":
    main()
