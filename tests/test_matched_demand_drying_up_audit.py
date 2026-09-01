from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import matched_demand_drying_up_audit as module
from matched_demand_drying_up_audit import AuditCase, MatchedPair, build_matches, summarize


def _case(*, bar_index=10, horizon=5, score=0.6, pressure=0.2, age=0, event_return=0.03) -> AuditCase:
    return AuditCase(
        symbol="TEST.NS",
        bar_index=bar_index,
        direction="bullish",
        state="healthy",
        horizon=horizon,
        score=score,
        pressure=pressure,
        vsa_age=age,
        forward_return=event_return,
        mfe=0.05,
        mae=0.02,
    )


def test_build_matches_uses_unique_controls() -> None:
    targets = [(_case(bar_index=10, event_return=0.03), True), (_case(bar_index=11, event_return=0.04), True)]
    controls = [(_case(bar_index=20, event_return=0.01), False), (_case(bar_index=21, event_return=0.02), False)]
    pairs = build_matches(targets + controls)
    assert len(pairs) == 2
    assert len({(p.control.symbol, p.control.bar_index, p.control.horizon) for p in pairs}) == 2


def test_build_matches_requires_context_match() -> None:
    target = _case()
    bad_direction = replace(target, bar_index=20, direction="bearish")
    pairs = build_matches([(target, True), (bad_direction, False)])
    assert pairs == []


def test_summarize_uses_target_horizon() -> None:
    pairs = [
        MatchedPair(target=_case(event_return=0.03), control=_case(bar_index=20, event_return=0.01), score_gap=0.0, pressure_gap=0.0, age_gap=0),
        MatchedPair(target=_case(bar_index=11, event_return=0.05), control=_case(bar_index=21, event_return=0.01), score_gap=0.0, pressure_gap=0.0, age_gap=0),
    ]
    rows = summarize(pairs)
    row = next(r for r in rows if r["horizon"] == 5)
    assert row["pairs"] == 2
    assert row["return_delta"] == 0.03


def test_scan_cases_marks_detector_events(monkeypatch) -> None:
    monkeypatch.setattr(module, "download_data", lambda symbol, refresh=False: None)
