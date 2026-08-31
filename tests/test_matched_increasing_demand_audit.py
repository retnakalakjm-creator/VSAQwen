from __future__ import annotations

from matched_increasing_demand_audit import AuditCase, MatchedPair, build_matches, summarize


def _case(*, bar: int, changed: bool, score: float = 0.2, pressure: float = 0.5, horizon: int = 5) -> tuple[AuditCase, bool]:
    return (
        AuditCase(
            symbol="TEST.NS",
            bar_index=bar,
            direction="bullish",
            state="healthy",
            change="True->False" if changed else "True->True",
            horizon=horizon,
            score=score,
            pressure=pressure,
            vsa_age=0,
            forward_return=0.10 if changed else 0.02,
            mfe=0.12,
            mae=0.03,
        ),
        changed,
    )


def test_build_matches_uses_same_context_and_horizon() -> None:
    pairs = build_matches(
        [_case(bar=10, changed=True), _case(bar=20, changed=False, score=0.21, pressure=0.49, horizon=5)],
    )
    assert len(pairs) == 1
    assert pairs[0].target.bar_index == 10
    assert pairs[0].control.bar_index == 20
    assert pairs[0].horizon == 5


def test_build_matches_rejects_context_outside_bands() -> None:
    pairs = build_matches(
        [_case(bar=10, changed=True), _case(bar=20, changed=False, score=0.50, pressure=0.49)],
        score_band=0.10,
    )
    assert pairs == []


def test_build_matches_rejects_horizon_mismatch() -> None:
    pairs = build_matches(
        [_case(bar=10, changed=True, horizon=3), _case(bar=20, changed=False, horizon=5)],
    )
    assert pairs == []


def test_summarize_returns_delta() -> None:
    target = _case(bar=10, changed=True)[0]
    control = _case(bar=20, changed=False)[0]
    pair = MatchedPair(target=target, control=control, horizon=5, score_gap=0.0, pressure_gap=0.0, age_gap=0)
    result = summarize([pair])
    assert result["pairs"] == 1
    assert result["target_mean_return"] == 0.10
    assert result["control_mean_return"] == 0.02
    assert result["return_delta"] == 0.08
