from __future__ import annotations

import pandas as pd
import pytest

from audit.daily_event_bc_upthrust_production_impact import (
    _contribution_rows,
    _event_contribution,
    _non_target_change_summary,
    _pair_row,
)


def _row(
    *,
    symbol: str = "AAA.NS",
    bar_index: int = 10,
    session: str = "2026-01-10T00:00:00",
    code: str,
    direction: str = "BEARISH",
    strength: float = 1.0,
    weight: float = 1.0,
    category: str = "SUPPLY",
    quality: float = 1.0,
    occurrence: int = 1,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "bar_index": bar_index,
        "session": session,
        "code": code,
        "category": category,
        "direction": direction,
        "strength": strength,
        "weight": weight,
        "quality": quality,
        "test_index": None,
        "recovery_index": None,
        "occurrence_on_bar_code": occurrence,
    }


def test_event_contribution_matches_primary_anchor_contract() -> None:
    frame = pd.DataFrame(
        [
            _row(
                code="buying_climax",
                strength=0.95,
                weight=1.2,
            ),
            _row(
                code="upthrust",
                strength=0.82,
                weight=0.8,
            ),
            _row(
                code="supply_coming_in",
                strength=0.8,
                weight=0.5,
            ),
            _row(
                code="structural_progression_weakening",
                strength=0.7,
                weight=0.4,
                category="TREND",
            ),
        ]
    )

    expected = (
        0.95 * 1.2
        + (0.8 * 0.5) * 0.15
        + (0.7 * 0.4) * 0.10
    )
    assert _event_contribution(frame) == pytest.approx(expected)


def test_non_target_stability_ignores_only_bc_and_upthrust() -> None:
    before = pd.DataFrame(
        [
            _row(code="buying_climax"),
            _row(code="upthrust"),
            _row(code="supply_coming_in", weight=0.7),
        ]
    )
    after = pd.DataFrame(
        [
            _row(code="buying_climax", bar_index=11),
            _row(code="upthrust", bar_index=12),
            _row(code="supply_coming_in", weight=0.7),
        ]
    )

    summary = _non_target_change_summary(before, after)
    assert summary.identity_drift_count == 0
    assert summary.unexpected_attribute_drift_count == 0
    assert summary.spring_conflict_quality_change_count == 0
    assert summary.disallowed_drift_count == 0

    changed_other = after.copy()
    changed_other.loc[
        changed_other["code"] == "supply_coming_in",
        "weight",
    ] = 0.9
    changed = _non_target_change_summary(before, changed_other)
    assert changed.identity_drift_count == 0
    assert changed.unexpected_attribute_drift_count == 1
    assert changed.disallowed_drift_count == 1


def test_spring_quality_change_is_allowed_only_when_conflict_changes() -> None:
    before = pd.DataFrame(
        [
            _row(
                code="spring",
                direction="BULLISH",
                category="DEMAND",
                quality=1.0,
            ),
        ]
    )
    after = pd.DataFrame(
        [
            _row(
                code="spring",
                direction="BULLISH",
                category="DEMAND",
                quality=0.5,
            ),
            _row(code="upthrust"),
        ]
    )

    summary = _non_target_change_summary(before, after)

    assert summary.identity_drift_count == 0
    assert summary.unexpected_attribute_drift_count == 0
    assert summary.spring_conflict_quality_change_count == 1
    assert summary.disallowed_drift_count == 0


def test_spring_quality_change_without_conflict_change_is_rejected() -> None:
    before = pd.DataFrame(
        [
            _row(
                code="spring",
                direction="BULLISH",
                category="DEMAND",
                quality=1.0,
            ),
        ]
    )
    after = pd.DataFrame(
        [
            _row(
                code="spring",
                direction="BULLISH",
                category="DEMAND",
                quality=0.5,
            ),
        ]
    )

    summary = _non_target_change_summary(before, after)

    assert summary.identity_drift_count == 0
    assert summary.unexpected_attribute_drift_count == 1
    assert summary.spring_conflict_quality_change_count == 0
    assert summary.disallowed_drift_count == 1


def test_pair_impact_reports_identical_then_partial_overlap() -> None:
    before_bc = {
        ("AAA.NS", 1, "2026-01-01T00:00:00"),
        ("AAA.NS", 2, "2026-01-02T00:00:00"),
    }
    before_ut = set(before_bc)
    after_bc = {
        ("AAA.NS", 2, "2026-01-02T00:00:00"),
        ("AAA.NS", 3, "2026-01-03T00:00:00"),
    }
    after_ut = {
        ("AAA.NS", 2, "2026-01-02T00:00:00"),
        ("AAA.NS", 4, "2026-01-04T00:00:00"),
    }

    before = _pair_row("BEFORE", before_bc, before_ut)
    after = _pair_row("AFTER", after_bc, after_ut)

    assert before.relationship == "IDENTICAL_FIRING_SET"
    assert before.jaccard == 1.0

    assert after.relationship == "PARTIAL_OVERLAP"
    assert after.overlap_count == 1
    assert after.union_count == 3
    assert after.jaccard == pytest.approx(1 / 3)


def test_contribution_changes_capture_new_and_removed_primary_events() -> None:
    before = pd.DataFrame(
        [
            _row(
                bar_index=10,
                code="buying_climax",
                strength=0.95,
                weight=1.0,
            ),
            _row(
                bar_index=10,
                code="upthrust",
                strength=0.82,
                weight=1.0,
            ),
        ]
    )
    after = pd.DataFrame(
        [
            _row(
                bar_index=10,
                code="buying_climax",
                strength=0.95,
                weight=1.0,
            ),
            _row(
                bar_index=12,
                session="2026-01-12T00:00:00",
                code="upthrust",
                strength=0.82,
                weight=1.0,
            ),
        ]
    )

    changes, symbols, total_before, total_after = _contribution_rows(
        before,
        after,
    )

    assert len(changes) == 1
    assert changes[0].bar_index == 12
    assert changes[0].before_contribution == 0.0
    assert changes[0].after_contribution == pytest.approx(0.82)

    assert len(symbols) == 1
    assert symbols[0].increased_event_group_count == 1
    assert total_before == pytest.approx(0.95)
    assert total_after == pytest.approx(0.95 + 0.82)
