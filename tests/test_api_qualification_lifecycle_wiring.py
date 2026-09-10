from __future__ import annotations

from types import SimpleNamespace

from api.schemas import QualificationDTO
from api.service import ProVSAService
from decision_context import build_decision_context
from models import EvidenceCategory, EvidenceCode, EvidenceDirection


LATEST_WEEK = "2026-04-06 00:00:00"


def _evidence(code: EvidenceCode | str) -> SimpleNamespace:
    return SimpleNamespace(
        code=code,
        category=EvidenceCategory.DEMAND,
        direction=EvidenceDirection.BULLISH,
        strength=0.8,
        weight=1.0,
        quality=1.0,
        observation="Fresh demand appeared against the active bearish qualification.",
        description="Test evidence object with production VSA fields.",
        bar_index=42,
        week_beginning=LATEST_WEEK,
        test_index=None,
        recovery_index=None,
    )


def _fake_candidate(
    *,
    qualification: str = "persistent_bearish",
    actionable: bool = False,
    scoring_evidence=None,
    scoring_evidence_age: int | None = 0,
    used_fallback_evidence: bool = False,
) -> SimpleNamespace:
    trend = SimpleNamespace(
        direction=SimpleNamespace(value="range"),
        state=SimpleNamespace(value="correcting"),
        strength=0.0,
        confidence=0.0,
        swing_count=0,
        hh_count=0,
        hl_count=0,
        lh_count=0,
        ll_count=0,
        swings=(),
        structural_swings=(),
    )
    return SimpleNamespace(
        evidence=SimpleNamespace(
            context=SimpleNamespace(trend=trend),
            evidence=(),
        ),
        qualification=SimpleNamespace(value=qualification),
        qualification_result=SimpleNamespace(
            evidence_codes=(),
            evidence_bar_indices=(),
        ),
        actionable=actionable,
        reason="Persistent qualification lifecycle test candidate.",
        signal_bar_anomaly=False,
        signal_bar_anomaly_reason=None,
        bar_index=42,
        week=LATEST_WEEK,
        execution_pending=False,
        campaign_evidence=(),
        qualifying_evidence=(),
        target_bar_evidence=(),
        scoring_evidence=tuple(scoring_evidence or ()),
        scoring_evidence_age=scoring_evidence_age,
        used_fallback_evidence=used_fallback_evidence,
        professional=SimpleNamespace(
            trend=0.0,
            supply=0.0,
            demand=0.0,
            effort=0.0,
            strength=0.0,
            weakness=0.0,
            confidence=0.0,
        ),
        net_strength=0.0,
        net_pressure=0.0,
        confidence=0.0,
    )


def test_qualification_dto_exposes_lifecycle_status_from_existing_candidate_fields() -> None:
    candidate = _fake_candidate(
        qualification="persistent_bearish",
        actionable=False,
        scoring_evidence=[_evidence(EvidenceCode.DEMAND_COMING_IN)],
        scoring_evidence_age=0,
    )

    lifecycle = ProVSAService._qualification_lifecycle(candidate)
    dto = QualificationDTO(
        qualification=candidate.qualification.value,
        actionable=candidate.actionable,
        reason=candidate.reason,
        evidence_codes=[],
        evidence_bar_indices=[],
        lifecycle=lifecycle,
    )

    assert dto.lifecycle is not None
    assert dto.lifecycle.status == "invalidated"
    assert dto.lifecycle.qualification_side == "bearish"
    assert dto.lifecycle.current_vsa_bias == "bullish"
    assert dto.lifecycle.opposing_event_codes == ["demand_coming_in"]
    assert dto.lifecycle.supporting_event_codes == []
    assert dto.lifecycle.production_safe is True


def test_decision_context_dto_can_carry_lifecycle_without_persistence_schema_change() -> None:
    candidate = _fake_candidate(
        qualification="persistent_bearish",
        actionable=False,
        scoring_evidence=[_evidence(EvidenceCode.INCREASING_DEMAND)],
        scoring_evidence_age=0,
    )
    context = build_decision_context(
        candidate,
        symbol="LT.NS",
        evaluated_at_utc="2026-09-10T12:00:00+00:00",
    )
    lifecycle = ProVSAService._qualification_lifecycle(candidate)

    dto = ProVSAService._decision_context_dto(context, lifecycle=lifecycle)

    assert dto.symbol == "LT.NS"
    assert dto.qualification_lifecycle is not None
    assert dto.qualification_lifecycle.status == "invalidated"
    assert dto.qualification_lifecycle.opposing_event_codes == ["increasing_demand"]


def test_cached_decision_context_dto_keeps_lifecycle_optional_without_scanning() -> None:
    candidate = _fake_candidate(qualification="unqualified")
    context = build_decision_context(
        candidate,
        symbol="TEST.NS",
        evaluated_at_utc="2026-09-10T12:00:00+00:00",
    )

    dto = ProVSAService._decision_context_dto(context)

    assert dto.qualification_lifecycle is None
