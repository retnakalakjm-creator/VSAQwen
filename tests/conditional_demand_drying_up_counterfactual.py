from __future__ import annotations

from dataclasses import dataclass

from background.qualification import PatternQualification
from models import EvidenceCode, TrendDirection, TrendState


TARGET_CONTEXTS = frozenset(
    {
        (TrendState.HEALTHY.value, "bearish"),
        (TrendState.HEALTHY.value, "bullish"),
        (TrendState.UNKNOWN.value, "bearish"),
        (TrendState.UNKNOWN.value, "bullish"),
        (TrendState.EXHAUSTED.value, "bearish"),
    }
)


@dataclass(frozen=True, slots=True)
class CounterfactualResult:
    suppressed: bool
    baseline_actionable: bool
    counterfactual_actionable: bool
    state: str
    direction: str


def direction_name(qualification: PatternQualification) -> str | None:
    if qualification is PatternQualification.PERSISTENT_BULLISH:
        return "bullish"
    if qualification is PatternQualification.PERSISTENT_BEARISH:
        return "bearish"
    return None


def has_demand_drying_up(candidate) -> bool:
    return EvidenceCode.DEMAND_DRYING_UP in {
        item.code for item in candidate.scoring_evidence
    } or EvidenceCode.DEMAND_DRYING_UP in {
        item.code for item in candidate.target_bar_evidence
    }


def is_target_context(trend, candidate) -> bool:
    direction = direction_name(candidate.qualification)
    if direction is None:
        return False
    return (trend.structure.state.value, direction) in TARGET_CONTEXTS


def apply_counterfactual(trend, candidate) -> CounterfactualResult:
    baseline_actionable = candidate.actionable
    direction = direction_name(candidate.qualification)
    if direction is None:
        return CounterfactualResult(
            suppressed=False,
            baseline_actionable=baseline_actionable,
            counterfactual_actionable=baseline_actionable,
            state=trend.structure.state.value,
            direction="unknown",
        )

    suppressed = baseline_actionable and has_demand_drying_up(candidate) and is_target_context(trend, candidate)
    return CounterfactualResult(
        suppressed=suppressed,
        baseline_actionable=baseline_actionable,
        counterfactual_actionable=baseline_actionable and not suppressed,
        state=trend.structure.state.value,
        direction=direction,
    )
