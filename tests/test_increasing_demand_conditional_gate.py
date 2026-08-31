from types import SimpleNamespace

import pytest

from models import EvidenceCategory, EvidenceCode, EvidenceDirection, TrendDirection, TrendState
from professional.scoring_engine import ProfessionalScoringEngine


def _trend(direction=TrendDirection.UP, state=TrendState.HEALTHY):
    return SimpleNamespace(
        structure=SimpleNamespace(
            direction=direction,
            state=state,
        )
    )


def _evidence(*codes, neutral_direction=False):
    items = []
    for code in codes:
        direction = EvidenceDirection.NEUTRAL if neutral_direction else (
            EvidenceDirection.BULLISH
            if code in {
                EvidenceCode.INCREASING_DEMAND,
                EvidenceCode.DEMAND_COMING_IN,
            }
            else EvidenceDirection.BEARISH
        )
        items.append(
            SimpleNamespace(
                direction=direction,
                code=code,
                category=EvidenceCategory.DEMAND,
            )
        )
    return SimpleNamespace(evidence=tuple(items))


def test_increasing_demand_passes_in_healthy_uptrend() -> None:
    confidence = ProfessionalScoringEngine._apply_increasing_demand_gate(
        confidence=0.70,
        trend=_trend(),
        evidence=_evidence(EvidenceCode.INCREASING_DEMAND),
    )
    assert confidence == pytest.approx(0.70)


def test_increasing_demand_gate_uses_code_semantics_when_direction_is_neutral() -> None:
    confidence = ProfessionalScoringEngine._apply_increasing_demand_gate(
        confidence=0.70,
        trend=_trend(),
        evidence=_evidence(EvidenceCode.INCREASING_DEMAND, neutral_direction=True),
    )
    assert confidence == pytest.approx(0.70)


def test_increasing_demand_is_blocked_outside_healthy_uptrend() -> None:
    confidence = ProfessionalScoringEngine._apply_increasing_demand_gate(
        confidence=0.70,
        trend=_trend(state=TrendState.CORRECTING),
        evidence=_evidence(EvidenceCode.INCREASING_DEMAND),
    )
    assert confidence == 0.0


def test_increasing_demand_is_blocked_in_downtrend() -> None:
    confidence = ProfessionalScoringEngine._apply_increasing_demand_gate(
        confidence=0.70,
        trend=_trend(direction=TrendDirection.DOWN),
        evidence=_evidence(EvidenceCode.INCREASING_DEMAND),
    )
    assert confidence == 0.0


def test_increasing_demand_gate_does_not_override_other_bullish_vsa_evidence() -> None:
    confidence = ProfessionalScoringEngine._apply_increasing_demand_gate(
        confidence=0.70,
        trend=_trend(state=TrendState.CORRECTING),
        evidence=_evidence(
            EvidenceCode.INCREASING_DEMAND,
            EvidenceCode.DEMAND_COMING_IN,
        ),
    )
    assert confidence == pytest.approx(0.70)


def test_increasing_demand_is_blocked_by_opposing_directional_vsa() -> None:
    confidence = ProfessionalScoringEngine._apply_increasing_demand_gate(
        confidence=0.70,
        trend=_trend(),
        evidence=_evidence(
            EvidenceCode.INCREASING_DEMAND,
            EvidenceCode.SUPPLY_COMING_IN,
        ),
    )
    assert confidence == 0.0


def test_non_increasing_demand_evidence_is_unchanged() -> None:
    confidence = ProfessionalScoringEngine._apply_increasing_demand_gate(
        confidence=0.70,
        trend=_trend(state=TrendState.CORRECTING),
        evidence=_evidence(EvidenceCode.DEMAND_COMING_IN),
    )
    assert confidence == pytest.approx(0.70)
