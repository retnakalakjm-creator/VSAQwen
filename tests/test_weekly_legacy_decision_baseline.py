from __future__ import annotations

import pytest

from background.qualification import (
    PatternQualification,
    PatternQualificationEngine,
    PatternQualificationResult,
)
from models import (
    Evidence,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
)
from scanner import ScannerEngine
from weekly_setup import WeeklySetup, WeeklySetupDirection


def _evidence(
    code: EvidenceCode,
    *,
    bar_index: int,
    direction: EvidenceDirection,
    category: EvidenceCategory,
) -> Evidence:
    return Evidence(
        code=code,
        category=category,
        direction=direction,
        strength=0.8,
        weight=1.0,
        observation=code.value,
        description="WF0 legacy-baseline fixture",
        bar_index=bar_index,
        week_beginning=f"W{bar_index:03d}",
    )


def _progression(bar_index: int, *, bullish: bool) -> Evidence:
    return _evidence(
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING
        if bullish
        else EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
        bar_index=bar_index,
        direction=(
            EvidenceDirection.BULLISH
            if bullish
            else EvidenceDirection.BEARISH
        ),
        category=EvidenceCategory.TREND,
    )


def _qualification(direction: PatternQualification) -> PatternQualificationResult:
    code = (
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING
        if direction is PatternQualification.PERSISTENT_BULLISH
        else EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING
    )
    return PatternQualificationResult(
        qualification=direction,
        is_actionable_evidence=True,
        reason="WF0 legacy qualification",
        evidence_codes=(code, code, code),
        evidence_bar_indices=(1, 5, 9),
    )


def test_legacy_structural_qualification_thresholds_are_frozen() -> None:
    assert PatternQualificationEngine.MIN_QUALIFYING_EVENTS == 3
    assert PatternQualificationEngine.MIN_EVENT_SPACING_BARS == 4

    engine = PatternQualificationEngine()

    state = engine.state_from_events(
        (
            _progression(1, bullish=True),
            _progression(5, bullish=True),
        )
    )
    assert engine.evaluate_state(state).qualification is PatternQualification.UNQUALIFIED

    state = engine.advance(state, (_progression(9, bullish=True),))
    result = engine.evaluate_state(state)

    assert result.qualification is PatternQualification.PERSISTENT_BULLISH
    assert result.is_actionable_evidence is True
    assert result.evidence_bar_indices == (1, 5, 9)


def test_legacy_opposing_progression_resets_active_campaign() -> None:
    engine = PatternQualificationEngine()
    state = engine.state_from_events(
        (
            _progression(1, bullish=True),
            _progression(5, bullish=True),
            _progression(9, bullish=True),
        )
    )
    assert engine.evaluate_state(state).qualification is PatternQualification.PERSISTENT_BULLISH

    opposing = _progression(10, bullish=False)
    state = engine.advance(state, (opposing,))

    assert state.active_events == (opposing,)
    assert engine.evaluate_state(state).qualification is PatternQualification.UNQUALIFIED


def test_legacy_scanner_window_and_freshness_contract_is_frozen() -> None:
    assert ScannerEngine.SCORING_LOOKBACK_BARS == 10
    assert ScannerEngine.MAX_ACTIONABLE_VSA_AGE == 3


def test_legacy_named_directional_vsa_sets_are_frozen() -> None:
    assert ScannerEngine._BULLISH_VSA_CODES == frozenset(
        {
            EvidenceCode.STOPPING_VOLUME,
            EvidenceCode.DEMAND_COMING_IN,
            EvidenceCode.INCREASING_DEMAND,
            EvidenceCode.HIDDEN_DEMAND,
            EvidenceCode.DEMAND_DRYING_UP,
            EvidenceCode.NO_SUPPLY,
            EvidenceCode.SPRING,
            EvidenceCode.TEST,
            EvidenceCode.SELLING_CLIMAX,
            EvidenceCode.SHAKEOUT,
        }
    )
    assert ScannerEngine._BEARISH_VSA_CODES == frozenset(
        {
            EvidenceCode.BUYING_CLIMAX,
            EvidenceCode.SUPPLY_COMING_IN,
            EvidenceCode.INCREASING_SUPPLY,
            EvidenceCode.HIDDEN_SUPPLY,
            EvidenceCode.SUPPLY_HIGH_VOLUME,
            EvidenceCode.SUPPLY_WIDE_SPREAD,
            EvidenceCode.SUPPLY_ABSORPTION,
            EvidenceCode.UPTHRUST,
            EvidenceCode.NO_DEMAND,
        }
    )


def test_legacy_read_only_evidence_does_not_become_named_vsa_confirmation() -> None:
    assert EvidenceCode.EFFORT_GT_RESULT in ScannerEngine._EFFORT_RESULT_READ_ONLY_CODES
    assert EvidenceCode.RESULT_GT_EFFORT in ScannerEngine._EFFORT_RESULT_READ_ONLY_CODES
    assert EvidenceCode.ABSORPTION in ScannerEngine._ABSORPTION_READ_ONLY_CODES

    readonly_codes = (
        ScannerEngine._EFFORT_RESULT_READ_ONLY_CODES
        | ScannerEngine._ABSORPTION_READ_ONLY_CODES
    )
    assert readonly_codes.isdisjoint(ScannerEngine._BULLISH_VSA_CODES)
    assert readonly_codes.isdisjoint(ScannerEngine._BEARISH_VSA_CODES)


def test_legacy_bullish_qualification_requires_aligned_named_vsa_without_opposition() -> None:
    qualification = _qualification(PatternQualification.PERSISTENT_BULLISH)
    bullish = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        bar_index=9,
        direction=EvidenceDirection.BULLISH,
        category=EvidenceCategory.DEMAND,
    )
    bearish = _evidence(
        EvidenceCode.SUPPLY_COMING_IN,
        bar_index=9,
        direction=EvidenceDirection.BEARISH,
        category=EvidenceCategory.SUPPLY,
    )
    absorption = _evidence(
        EvidenceCode.ABSORPTION,
        bar_index=9,
        direction=EvidenceDirection.BULLISH,
        category=EvidenceCategory.ABSORPTION,
    )

    assert ScannerEngine._vsa_supports_qualification(qualification, (bullish,)) is True
    assert ScannerEngine._vsa_supports_qualification(qualification, (absorption,)) is False
    assert ScannerEngine._vsa_supports_qualification(qualification, (bullish, bearish)) is False


def test_legacy_bearish_qualification_requires_aligned_named_vsa_without_opposition() -> None:
    qualification = _qualification(PatternQualification.PERSISTENT_BEARISH)
    bearish = _evidence(
        EvidenceCode.SUPPLY_COMING_IN,
        bar_index=9,
        direction=EvidenceDirection.BEARISH,
        category=EvidenceCategory.SUPPLY,
    )
    bullish = _evidence(
        EvidenceCode.DEMAND_COMING_IN,
        bar_index=9,
        direction=EvidenceDirection.BULLISH,
        category=EvidenceCategory.DEMAND,
    )

    assert ScannerEngine._vsa_supports_qualification(qualification, (bearish,)) is True
    assert ScannerEngine._vsa_supports_qualification(qualification, (bearish, bullish)) is False


def test_weekly_setup_remains_coupled_to_legacy_persistent_qualification() -> None:
    bullish = WeeklySetup(
        setup_id="TEST:2026-01-05:bullish",
        symbol="TEST",
        direction=WeeklySetupDirection.BULLISH,
        signal_week="2026-01-05",
        qualification=PatternQualification.PERSISTENT_BULLISH,
        weekly_confidence=0.7,
        weekly_net_strength=0.6,
        weekly_net_pressure=0.4,
    )
    assert bullish.qualification is PatternQualification.PERSISTENT_BULLISH

    with pytest.raises(ValueError, match="direction must match"):
        WeeklySetup(
            setup_id="TEST:2026-01-05:bullish",
            symbol="TEST",
            direction=WeeklySetupDirection.BULLISH,
            signal_week="2026-01-05",
            qualification=PatternQualification.PERSISTENT_BEARISH,
            weekly_confidence=0.7,
            weekly_net_strength=0.6,
            weekly_net_pressure=0.4,
        )
