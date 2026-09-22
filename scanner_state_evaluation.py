from __future__ import annotations

from background.qualification import PatternQualificationEngine, PatternQualificationState
from model.evidence_result_model import EvidenceResult
from models import Evidence
from scanner import ANOMALY_SIGNAL_BAR_REASON, ScannerCandidate, ScannerEngine
from scanner_policy import DEFAULT_VSA_FRESHNESS_POLICY
from trend import TrendResult


def evaluate_from_qualification_state(
    scanner: ScannerEngine,
    qualification_engine: PatternQualificationEngine,
    *,
    trend: TrendResult,
    evidence: EvidenceResult,
    qualification_state: PatternQualificationState,
    recent_vsa_evidence: tuple[Evidence, ...] = (),
    bar_index: int | None = None,
    week: str | None = None,
    execution_bar_index: int | None = None,
    execution_week: str | None = None,
    signal_bar_anomaly: bool = False,
) -> ScannerCandidate:
    """Evaluate one candidate directly from explicit causal qualification state.

    This mirrors ``ScannerEngine.evaluate`` while removing the transition path's
    need to synthesize ``EvidenceResult`` history solely for qualification.
    The legacy scanner API remains unchanged for compatibility and parity tests.
    """

    qualification = qualification_engine.evaluate_state(qualification_state)
    structural_qualification_current = scanner._qualification_is_current(
        qualification,
        bar_index,
    )
    target_bar_evidence = scanner._target_bar_evidence(evidence, bar_index)
    qualifying_evidence = qualification_engine.qualifying_events(qualification_state)
    scoring_evidence = scanner._scoring_evidence(
        evidence,
        bar_index,
        qualifying_evidence,
        historical_evidence=recent_vsa_evidence,
    )
    campaign_evidence = scanner._campaign_evidence(
        evidence,
        recent_vsa_evidence,
        qualifying_evidence,
    )
    professional = scanner._professional.calculate(
        trend=trend,
        evidence=EvidenceResult(
            context=evidence.context,
            evidence=scoring_evidence,
        ),
    )

    if qualification.is_actionable_evidence:
        scoring_bar_index = scanner._scoring_bar_index(scoring_evidence)
        if not structural_qualification_current and not scoring_evidence:
            qualification = scanner._invalidate_stale_qualification(qualification)
        elif scoring_bar_index is None:
            qualification = scanner._invalidate_missing_vsa_confirmation(qualification)
        else:
            scoring_age = DEFAULT_VSA_FRESHNESS_POLICY.age(
                scoring_bar_index=scoring_bar_index,
                target_bar_index=bar_index,
            )
            if not scanner._vsa_confirmation_is_current(
                scoring_evidence,
                bar_index,
            ):
                qualification = scanner._invalidate_stale_vsa_confirmation(
                    qualification,
                    scoring_age
                    if scoring_age is not None
                    else scanner.MAX_ACTIONABLE_VSA_AGE + 1,
                )
            elif scanner._vsa_conflicts_with_qualification(
                qualification,
                professional,
                scoring_evidence,
            ):
                qualification = scanner._invalidate_vsa_conflict(
                    qualification,
                    professional,
                )
            elif not scanner._vsa_supports_qualification(
                qualification,
                scoring_evidence,
            ):
                qualification = scanner._invalidate_missing_vsa_confirmation(
                    qualification
                )
            elif not structural_qualification_current:
                qualification = scanner._qualify_vsa_continuation(
                    qualification,
                    scoring_bar_index,
                    scoring_age,
                )

    scoring_bar_index = scanner._scoring_bar_index(scoring_evidence)
    return ScannerCandidate(
        evidence=evidence,
        professional=professional,
        qualification_result=qualification,
        target_bar_evidence=target_bar_evidence,
        campaign_evidence=campaign_evidence,
        qualifying_evidence=qualifying_evidence,
        scoring_evidence=scoring_evidence,
        scoring_bar_index=scoring_bar_index,
        scoring_evidence_age=(
            None
            if scoring_bar_index is None or bar_index is None
            else bar_index - scoring_bar_index
        ),
        used_fallback_evidence=(
            scoring_bar_index is not None
            and bar_index is not None
            and scoring_bar_index != bar_index
        ),
        bar_index=bar_index,
        week=week,
        execution_bar_index=execution_bar_index,
        execution_week=execution_week,
        signal_bar_anomaly=signal_bar_anomaly,
        signal_bar_anomaly_reason=(
            ANOMALY_SIGNAL_BAR_REASON if signal_bar_anomaly else None
        ),
    )


__all__ = ["evaluate_from_qualification_state"]
