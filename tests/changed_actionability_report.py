from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from model.evidence_result_model import EvidenceResult
from models import EvidenceCode
from scanner import ScannerCandidate, ScannerEngine
from tests.decision_outcome_labeling import DecisionOutcome, label_outcome
from tests.decision_outcome_audit import compare_candidate_outcome


CONFIRMATION_ONLY_CODES = frozenset(
    {
        EvidenceCode.DEMAND_COMING_IN,
        EvidenceCode.INCREASING_DEMAND,
        EvidenceCode.HIDDEN_DEMAND,
        EvidenceCode.DEMAND_DRYING_UP,
        EvidenceCode.NO_SUPPLY,
        EvidenceCode.SPRING,
        EvidenceCode.TEST,
        EvidenceCode.SELLING_CLIMAX,
    }
)


@dataclass(frozen=True, slots=True)
class ChangedActionabilityCase:
    bar_index: int
    baseline: ScannerCandidate
    masked: ScannerCandidate
    outcome: DecisionOutcome
    confirmation_only_codes: tuple[str, ...]

    @property
    def actionability_change(self) -> str:
        return f"{self.baseline.actionable}->{self.masked.actionable}"

    @property
    def score_delta(self) -> float:
        return self.masked.base_score - self.baseline.base_score

    @property
    def pressure_delta(self) -> float:
        return self.masked.net_pressure - self.baseline.net_pressure

    @property
    def decision_effect(self) -> str:
        if self.baseline.actionable and not self.masked.actionable:
            return "confirmation_removed_actionability"
        if not self.baseline.actionable and self.masked.actionable:
            return "confirmation_added_actionability"
        return "unchanged"


def confirmation_only_codes(evidence: EvidenceResult) -> tuple[str, ...]:
    return tuple(
        sorted(
            str(item.code)
            for item in evidence.evidence
            if item.code in CONFIRMATION_ONLY_CODES
        )
    )


def analyze_changed_actionability(
    scanner: ScannerEngine,
    *,
    trend,
    evidence: EvidenceResult,
    history,
    metrics: pd.DataFrame,
    bar_index: int,
    direction: int,
    horizon: int,
) -> ChangedActionabilityCase | None:
    comparison = compare_candidate_outcome(
        scanner,
        trend=trend,
        evidence=evidence,
        history=history,
        metrics=metrics,
        bar_index=bar_index,
        direction=direction,
        horizon=horizon,
    )
    if not comparison.changed_actionability:
        return None
    return ChangedActionabilityCase(
        bar_index=bar_index,
        baseline=comparison.baseline,
        masked=comparison.masked,
        outcome=comparison.outcome,
        confirmation_only_codes=confirmation_only_codes(evidence),
    )


def summarize_cases(cases: list[ChangedActionabilityCase]) -> dict[str, float | int]:
    complete = [case for case in cases if case.outcome.complete]
    removed = [case for case in complete if case.decision_effect == "confirmation_removed_actionability"]
    added = [case for case in complete if case.decision_effect == "confirmation_added_actionability"]

    def _mean(items: list[ChangedActionabilityCase], attr: str) -> float:
        if not items:
            return 0.0
        return sum(float(getattr(case.outcome, attr) or 0.0) for case in items) / len(items)

    return {
        "cases": len(cases),
        "complete": len(complete),
        "confirmation_removed_actionability": len(removed),
        "confirmation_added_actionability": len(added),
        "removed_mean_forward_return": _mean(removed, "forward_return"),
        "added_mean_forward_return": _mean(added, "forward_return"),
        "removed_mean_mfe": _mean(removed, "maximum_favorable_excursion"),
        "added_mean_mfe": _mean(added, "maximum_favorable_excursion"),
        "removed_mean_mae": _mean(removed, "maximum_adverse_excursion"),
        "added_mean_mae": _mean(added, "maximum_adverse_excursion"),
    }
