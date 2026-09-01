from __future__ import annotations

from types import SimpleNamespace

from background.qualification import PatternQualification
from conditional_demand_drying_up_counterfactual import (
    TARGET_CONTEXTS,
    apply_counterfactual,
    has_demand_drying_up,
    is_target_context,
)
from models import EvidenceCode, TrendDirection, TrendState


def _candidate(*, actionable=True, qualification=PatternQualification.PERSISTENT_BULLISH, code=EvidenceCode.DEMAND_DRYING_UP):
    evidence = SimpleNamespace(code=code)
    return SimpleNamespace(
        actionable=actionable,
        qualification=qualification,
        scoring_evidence=(evidence,),
        target_bar_evidence=(evidence,),
    )


def _trend(state=TrendState.HEALTHY, direction=TrendDirection.UP):
    return SimpleNamespace(structure=SimpleNamespace(state=state, direction=direction))


def test_target_context_contains_expected_contexts() -> None:
    assert ("healthy", "bullish") in TARGET_CONTEXTS
    assert ("healthy", "bearish") in TARGET_CONTEXTS
    assert ("unknown", "bullish") in TARGET_CONTEXTS
    assert ("exhausted", "bearish") in TARGET_CONTEXTS


def test_counterfactual_suppresses_actionable_drying_up_in_target_context() -> None:
    result = apply_counterfactual(_trend(), _candidate())
    assert result.suppressed is True
    assert result.baseline_actionable is True
    assert result.counterfactual_actionable is False


def test_counterfactual_keeps_non_target_context_actionable() -> None:
    result = apply_counterfactual(
        _trend(TrendState.CORRECTING, TrendDirection.UP),
        _candidate(),
    )
    assert result.suppressed is False
    assert result.counterfactual_actionable is True


def test_counterfactual_does_not_suppress_non_actionable_candidate() -> None:
    result = apply_counterfactual(_trend(), _candidate(actionable=False))
    assert result.suppressed is False
    assert result.counterfactual_actionable is False


def test_helpers_require_demand_drying_up_event() -> None:
    assert has_demand_drying_up(_candidate()) is True
    assert is_target_context(_trend(), _candidate()) is True
