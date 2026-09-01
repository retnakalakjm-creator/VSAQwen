from types import SimpleNamespace

import pytest

from models import EvidenceCategory, EvidenceCode, TrendDirection, TrendState
from professional.scoring_engine import ProfessionalScoringEngine


def _trend(direction=TrendDirection.UP, state=TrendState.CORRECTING):
    return SimpleNamespace(structure=SimpleNamespace(direction=direction, state=state))


def _evidence(*codes):
    return SimpleNamespace(
        evidence=tuple(
            SimpleNamespace(code=code, category=EvidenceCategory.DEMAND)
            for code in codes
        )
    )


def test_demand_coming_in_is_suppressed_in_correcting_bullish_context() -> None:
    confidence = ProfessionalScoringEngine._apply_demand_coming_in_gate(
        confidence=0.70,
        trend=_trend(),
        evidence=_evidence(EvidenceCode.DEMAND_COMING_IN),
    )
    assert confidence == 0.0


def test_demand_coming_in_is_unchanged_in_healthy_bullish_context() -> None:
    confidence = ProfessionalScoringEngine._apply_demand_coming_in_gate(
        confidence=0.70,
        trend=_trend(state=TrendState.HEALTHY),
        evidence=_evidence(EvidenceCode.DEMAND_COMING_IN),
    )
    assert confidence == pytest.approx(0.70)


def test_demand_coming_in_is_unchanged_in_bearish_direction() -> None:
    confidence = ProfessionalScoringEngine._apply_demand_coming_in_gate(
        confidence=0.70,
        trend=_trend(direction=TrendDirection.DOWN),
        evidence=_evidence(EvidenceCode.DEMAND_COMING_IN),
    )
    assert confidence == pytest.approx(0.70)


def test_other_demand_evidence_is_unchanged() -> None:
    confidence = ProfessionalScoringEngine._apply_demand_coming_in_gate(
        confidence=0.70,
        trend=_trend(),
        evidence=_evidence(EvidenceCode.INCREASING_DEMAND),
    )
    assert confidence == pytest.approx(0.70)
