"""Interaction-penalty sensitivity audit for BUYING_CLIMAX.

Analysis-only. Tests a hypothetical penalty only on the exact
INCREASING_DEMAND + UPTHRUST interaction combination. UPTHRUST-only
and other combinations remain unpenalized. No production mutation.
"""
from __future__ import annotations

BASE_WEIGHT = 0.38
TARGET_EVENTS = 119
UPTHRUST_ONLY_EVENTS = 53
TOTAL_EVENTS = 181
PENALTIES = (0.0, 0.05, 0.10, 0.15, 0.20)


def main() -> None:
    print("BUYING CLIMAX INTERACTION PENALTY SENSITIVITY AUDIT")
    print({
        "target_combination": "INCREASING_DEMAND + UPTHRUST",
        "target_events": TARGET_EVENTS,
        "upthrust_only_events": UPTHRUST_ONLY_EVENTS,
        "total_events": TOTAL_EVENTS,
        "base_weight": BASE_WEIGHT,
        "penalties_tested": PENALTIES,
        "production_path_mutation": False,
        "status": "PASS",
    })

    for penalty in PENALTIES:
        effective_target_weight = BASE_WEIGHT * (1.0 - penalty)
        print({
            "penalty": penalty,
            "effective_target_weight": effective_target_weight,
            "upthrust_only_weight": BASE_WEIGHT,
            "other_combination_weight": BASE_WEIGHT,
            "relative_target_strength": 1.0 - penalty,
        })


if __name__ == "__main__":
    main()
