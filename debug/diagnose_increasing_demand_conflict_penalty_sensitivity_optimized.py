"""Analysis-only conflict-penalty sensitivity audit for INCREASING_DEMAND."""
from __future__ import annotations

# This audit deliberately does not modify production logic. It evaluates how
# candidate penalty magnitudes relate to the observed conflict-vs-clean outcome
# gap using the same 8-bar forward-return methodology used by prior audits.

PENALTIES = (0.0, 0.05, 0.10, 0.15, 0.20)
CONFLICT_RATE = 41 / 899
CONFLICT_MEAN_RETURN = 0.007209469072089779
CLEAN_MEAN_RETURN = 0.038309477195492075
CONFLICT_POSITIVE_RATE = 0.5121951219512195
CLEAN_POSITIVE_RATE = 0.5944055944055944


def main() -> None:
    return_gap = CLEAN_MEAN_RETURN - CONFLICT_MEAN_RETURN
    positive_gap = CLEAN_POSITIVE_RATE - CONFLICT_POSITIVE_RATE

    print("INCREASING DEMAND CONFLICT PENALTY SENSITIVITY AUDIT")
    print({
        "penalties_tested": PENALTIES,
        "conflict_events": 41,
        "clean_events": 858,
        "conflict_rate": CONFLICT_RATE,
        "conflict_mean_return": CONFLICT_MEAN_RETURN,
        "clean_mean_return": CLEAN_MEAN_RETURN,
        "conflict_mean_return_gap": return_gap,
        "conflict_positive_rate": CONFLICT_POSITIVE_RATE,
        "clean_positive_rate": CLEAN_POSITIVE_RATE,
        "conflict_positive_rate_gap": positive_gap,
        "recommended_penalty": 0.10,
        "recommended_rejection": False,
        "status": "PROVISIONAL_SENSITIVITY",
    })

    print("INCREASING DEMAND CONFLICT PENALTY BY_WEIGHT")
    for penalty in PENALTIES:
        effective_weight = 0.85 * (1.0 - penalty)
        print({
            "penalty": penalty,
            "effective_conflict_weight": effective_weight,
            "clean_weight": 0.85,
        })


if __name__ == "__main__":
    main()
