from __future__ import annotations

from matched_demand_coming_in_audit import AuditCase, MatchedPair, build_matches, summarize


def _case(*, bar: int, event: bool, horizon: int = 5, score: float = 0.20, pressure: float = 0.50) -> tuple[AuditCase, bool]:
    return AuditCase(
        symbol="TEST.NS",
        bar_index=bar,
        direction="bullish",
        state="healthy",
        horizon=horizon,
        score=score,
        pressure=pressure,
        vsa_age=0,
        forward_return=0.10 if event else 0.02,
        mfe=0.12,
        mae=0.03,
    ), event


def test_build_matches_same_context_and_horizon() -> None:
    pairs = build_matches([
        _case(bar=10, event=True),
        _case(bar=20, event=False, score=0.21, pressure=0.49),
    ])
    assert len(pairs) == 1
    assert pairs[0].target.bar_index == 10
    assert pairs[0].control.bar_index == 20


def test_build_matches_rejects_horizon_mismatch() -> None:
    pairs = build_matches([
        _case(bar=10, event=True, horizon=3),
        _case(bar=20, event=False, horizon=5),
    ])
    assert pairs == []


def test_build_matches_rejects_context_outside_bands() -> None:
    pairs = build_matches([
        _case(bar=10, event=True),
        _case(bar=20, event=False, score=0.50),
    ], score_band=0.10)
    assert pairs == []


def test_controls_are_not_reused() -> None:
    pairs = build_matches([
        _case(bar=10, event=True),
        _case(bar=11, event=True),
        _case(bar=20, event=False),
    ])
    assert len(pairs) == 1
    assert len({p.control.bar_index for p in pairs}) == 1


def test_summarize_returns_target_control_delta() -> None:
    target = _case(bar=10, event=True)[0]
    control = _case(bar=20, event=False)[0]
    pair = MatchedPair(target=target, control=control, score_gap=0.0, pressure_gap=0.0, age_gap=0)
    result = summarize([pair])
    assert result[0]["pairs"] == 1
    assert result[0]["return_delta"] == 0.08
