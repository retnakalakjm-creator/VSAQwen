from types import SimpleNamespace

import config
from models import EvidenceCategory, EvidenceCode, TrendDirection, TrendState
from professional.scoring_engine import ProfessionalScoringEngine


def _trend(direction: TrendDirection, state: TrendState):
    return SimpleNamespace(
        structure=SimpleNamespace(
            direction=direction,
            state=state,
        )
    )


def _evidence(*codes):
    return SimpleNamespace(
        evidence=tuple(SimpleNamespace(code=code) for code in codes)
    )


def test_increasing_demand_remains_confirmation_only() -> None:
    assert EvidenceCode.INCREASING_DEMAND not in config.DEMAND_EVIDENCE_WEIGHTS

    result = _evidence(EvidenceCode.INCREASING_DEMAND)
    confidence = 0.65

    assert ProfessionalScoringEngine._apply_increasing_demand_gate(
        confidence=confidence,
        trend=_trend(TrendDirection.UP, TrendState.HEALTHY),
        evidence=result,
    ) == confidence

    for direction, state in (
        (TrendDirection.UP, TrendState.CORRECTING),
        (TrendDirection.UP, TrendState.EXHAUSTED),
        (TrendDirection.DOWN, TrendState.HEALTHY),
        (TrendDirection.RANGE, TrendState.UNKNOWN),
    ):
        assert ProfessionalScoringEngine._apply_increasing_demand_gate(
            confidence=confidence,
            trend=_trend(direction, state),
            evidence=result,
        ) == 0.0


def test_demand_coming_in_policy_is_soft_not_a_global_rejection() -> None:
    result = _evidence(EvidenceCode.DEMAND_COMING_IN)
    confidence = 0.70

    assert ProfessionalScoringEngine._apply_demand_coming_in_gate(
        confidence=confidence,
        trend=_trend(TrendDirection.UP, TrendState.HEALTHY),
        evidence=result,
    ) == confidence

    assert ProfessionalScoringEngine._apply_demand_coming_in_gate(
        confidence=confidence,
        trend=_trend(TrendDirection.UP, TrendState.CORRECTING),
        evidence=result,
    ) == 0.0

    assert ProfessionalScoringEngine._apply_demand_coming_in_gate(
        confidence=confidence,
        trend=_trend(TrendDirection.DOWN, TrendState.CORRECTING),
        evidence=result,
    ) == confidence


def test_absorption_is_production_connected_but_non_scoring() -> None:
    assert config.EFFORT_EVIDENCE_WEIGHTS[EvidenceCode.ABSORPTION] == 0.0

    result = SimpleNamespace(
        evidence=(
            SimpleNamespace(
                category=EvidenceCategory.ABSORPTION,
                code=EvidenceCode.ABSORPTION,
            ),
        )
    )

    assert ProfessionalScoringEngine._score_effort(result) == 0.0


def test_absorption_cannot_change_professional_effort_at_zero_weight() -> None:
    baseline = SimpleNamespace(
        evidence=(
            SimpleNamespace(
                category=EvidenceCategory.EFFORT,
                code=EvidenceCode.EFFORT_GT_RESULT,
            ),
        )
    )
    with_absorption = SimpleNamespace(
        evidence=(
            SimpleNamespace(
                category=EvidenceCategory.EFFORT,
                code=EvidenceCode.EFFORT_GT_RESULT,
            ),
            SimpleNamespace(
                category=EvidenceCategory.ABSORPTION,
                code=EvidenceCode.ABSORPTION,
            ),
        )
    )

    assert ProfessionalScoringEngine._score_effort(with_absorption) == (
        ProfessionalScoringEngine._score_effort(baseline)
    )


def test_demand_drying_up_has_no_production_scoring_weight() -> None:
    assert EvidenceCode.DEMAND_DRYING_UP not in config.DEMAND_EVIDENCE_WEIGHTS


def test_scoring_policy_codes_are_explicitly_partitioned() -> None:
    assert EvidenceCode.INCREASING_DEMAND not in config.DEMAND_EVIDENCE_WEIGHTS
    assert EvidenceCode.DEMAND_COMING_IN not in config.DEMAND_EVIDENCE_WEIGHTS
    assert EvidenceCode.DEMAND_DRYING_UP not in config.DEMAND_EVIDENCE_WEIGHTS
    assert config.EFFORT_EVIDENCE_WEIGHTS[EvidenceCode.ABSORPTION] == 0.0
