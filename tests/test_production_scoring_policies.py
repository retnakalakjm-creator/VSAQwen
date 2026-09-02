from types import SimpleNamespace

import config
from models import EvidenceCategory, EvidenceCode, TrendDirection, TrendState
from professional.scoring_engine import ProfessionalScoringEngine


def _trend(direction: TrendDirection, state: TrendState):
    return SimpleNamespace(
        structure=SimpleNamespace(
            direction=direction,
            state=state,
            strength=0.8,
            confidence=0.8,
        )
    )


def _evidence(*codes):
    return SimpleNamespace(
        evidence=tuple(
            SimpleNamespace(code=code, category=EvidenceCategory.DEMAND)
            for code in codes
        )
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


def test_end_to_end_increasing_demand_gate_controls_actionability_confidence() -> None:
    evidence = _evidence(EvidenceCode.INCREASING_DEMAND)
    engine = ProfessionalScoringEngine()

    healthy = engine.calculate(
        _trend(TrendDirection.UP, TrendState.HEALTHY),
        evidence,
    )
    correcting = engine.calculate(
        _trend(TrendDirection.UP, TrendState.CORRECTING),
        evidence,
    )

    assert healthy.scores.confidence > 0.0
    assert correcting.scores.confidence == 0.0


def test_end_to_end_demand_coming_in_gate_suppresses_only_validated_regime() -> None:
    evidence = _evidence(EvidenceCode.DEMAND_COMING_IN)
    engine = ProfessionalScoringEngine()

    healthy = engine.calculate(
        _trend(TrendDirection.UP, TrendState.HEALTHY),
        evidence,
    )
    correcting = engine.calculate(
        _trend(TrendDirection.UP, TrendState.CORRECTING),
        evidence,
    )
    down = engine.calculate(
        _trend(TrendDirection.DOWN, TrendState.CORRECTING),
        evidence,
    )

    assert healthy.scores.confidence > 0.0
    assert correcting.scores.confidence == 0.0
    assert down.scores.confidence > 0.0


def test_confirmation_only_demand_events_do_not_change_professional_pressure() -> None:
    engine = ProfessionalScoringEngine()
    baseline = engine.calculate(
        _trend(TrendDirection.UP, TrendState.HEALTHY),
        _evidence(),
    )
    with_increasing = engine.calculate(
        _trend(TrendDirection.UP, TrendState.HEALTHY),
        _evidence(EvidenceCode.INCREASING_DEMAND),
    )
    with_dci = engine.calculate(
        _trend(TrendDirection.UP, TrendState.HEALTHY),
        _evidence(EvidenceCode.DEMAND_COMING_IN),
    )

    for result in (with_increasing, with_dci):
        assert result.scores.demand == baseline.scores.demand
        assert result.scores.net_strength == baseline.scores.net_strength
        assert result.scores.net_pressure == baseline.scores.net_pressure


def test_increasing_demand_cannot_improve_a_non_healthy_regime() -> None:
    engine = ProfessionalScoringEngine()
    baseline = engine.calculate(
        _trend(TrendDirection.UP, TrendState.CORRECTING),
        _evidence(),
    )
    with_event = engine.calculate(
        _trend(TrendDirection.UP, TrendState.CORRECTING),
        _evidence(EvidenceCode.INCREASING_DEMAND),
    )

    assert with_event.scores.demand == baseline.scores.demand
    assert with_event.scores.net_strength == baseline.scores.net_strength
    assert with_event.scores.confidence == 0.0
