from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from model.evidence_result_model import EvidenceResult
from models import EvidenceCode
from scanner import ScannerCandidate, ScannerEngine
from tests.decision_outcome_labeling import DecisionOutcome, label_outcome


CONFIRMATION_ONLY_CODES = frozenset({
    EvidenceCode.DEMAND_COMING_IN,
    EvidenceCode.INCREASING_DEMAND,
    EvidenceCode.HIDDEN_DEMAND,
    EvidenceCode.DEMAND_DRYING_UP,
    EvidenceCode.NO_SUPPLY,
    EvidenceCode.SPRING,
    EvidenceCode.TEST,
    EvidenceCode.SELLING_CLIMAX,
})


@dataclass(frozen=True, slots=True)
class DecisionOutcomeComparison:
    bar_index: int
    direction: int
    baseline: ScannerCandidate
    masked: ScannerCandidate
    outcome: DecisionOutcome

    @property
    def changed_actionability(self) -> bool:
        return self.baseline.actionable != self.masked.actionable

    @property
    def changed_score(self) -> bool:
        return self.baseline.base_score != self.masked.base_score



def mask_confirmation_only(evidence: EvidenceResult) -> EvidenceResult:
    retained = tuple(
        item for item in evidence.evidence
        if item.code not in CONFIRMATION_ONLY_CODES
    )
    return EvidenceResult(context=evidence.context, evidence=retained)


def compare_candidate_outcome(
    scanner: ScannerEngine,
    *,
    trend,
    evidence: EvidenceResult,
    history,
    metrics: pd.DataFrame,
    bar_index: int,
    direction: int,
    horizon: int,
) -> DecisionOutcomeComparison:
    baseline = scanner.evaluate(
        trend=trend,
        evidence=evidence,
        history=history,
        bar_index=bar_index,
        week=None,
    )
    masked = scanner.evaluate(
        trend=trend,
        evidence=mask_confirmation_only(evidence),
        history=history,
        bar_index=bar_index,
        week=None,
    )
    outcome = label_outcome(
        metrics,
        signal_index=bar_index,
        direction=direction,
        horizon=horizon,
    )
    return DecisionOutcomeComparison(
        bar_index=bar_index,
        direction=direction,
        baseline=baseline,
        masked=masked,
        outcome=outcome,
    )
