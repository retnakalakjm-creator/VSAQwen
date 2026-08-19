"""Conservative weighting audit for DEMAND_COMING_IN.

Analysis-only. Combines completed audit evidence into a bounded provisional
weight recommendation. It does not register or enable a production weight.
"""
from __future__ import annotations

# Evidence inputs are intentionally explicit so the recommendation is auditable.
SEMANTIC_QUALITY = 0.8540925266903915
DECISION_LIFT = 0.05517004720462604
MEAN_RETURN_LIFT = 0.0034635360061431447
TEMPORAL_LIFTS = (-0.0796974755345996, 0.07070907933936887, 0.11195248700816629, 0.20118083034985246)
INTERACTION_CONFLICT_PENALTY = 0.0

# Current production demand scale anchors.
PRIMARY_DEMAND_WEIGHT = 1.0


def main() -> None:
    positive_temporal_windows = sum(value > 0 for value in TEMPORAL_LIFTS)
    temporal_mean = sum(TEMPORAL_LIFTS) / len(TEMPORAL_LIFTS)

    # Conservative scoring: semantic validity + decision value support a weight;
    # unstable temporal behavior limits the upper bound; return lift is modest.
    score = (
        0.40 * SEMANTIC_QUALITY
        + 0.40 * max(0.0, DECISION_LIFT / 0.10)
        + 0.20 * max(0.0, MEAN_RETURN_LIFT / 0.01)
    )

    if SEMANTIC_QUALITY >= 0.80 and DECISION_LIFT >= 0.05:
        lower = 0.25
        upper = 0.50
    else:
        lower = 0.10
        upper = 0.25

    if positive_temporal_windows < 3:
        upper = min(upper, 0.25)

    if temporal_mean <= 0:
        upper = min(upper, 0.20)

    recommended = round((lower + upper) / 2, 2)

    print("DEMAND COMING IN WEIGHTING AUDIT")
    print({
        "status": "PROVISIONAL",
        "production_weight": 0.0,
        "semantic_quality": SEMANTIC_QUALITY,
        "decision_lift": DECISION_LIFT,
        "mean_return_lift": MEAN_RETURN_LIFT,
        "temporal_lifts": TEMPORAL_LIFTS,
        "positive_temporal_windows": positive_temporal_windows,
        "temporal_mean": temporal_mean,
        "interaction_conflict_penalty": INTERACTION_CONFLICT_PENALTY,
        "normalized_audit_score": round(score, 4),
        "provisional_weight_range": (lower, upper),
        "recommended_audit_weight": recommended,
        "production_action": "DO_NOT_REGISTER_YET",
    })


if __name__ == "__main__":
    main()
