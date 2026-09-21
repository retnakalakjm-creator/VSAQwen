from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import pytest

from audit.daily_event_no_supply_alternate_context_profile import (
    GROUP_LATEST,
    GROUP_PRIOR,
    NoSupplyAlternateCandidateContext,
    build_categorical_shift_rows,
    build_context_outcome_rows,
    build_continuous_shift_rows,
)


def _context(
    *,
    symbol: str,
    session: str,
    group: str,
    trend_state: str,
    structural_pattern: str,
    close_position: str,
    trend_strength: float,
    volume_ratio: float,
) -> NoSupplyAlternateCandidateContext:
    return NoSupplyAlternateCandidateContext(
        symbol=symbol,
        session=session,
        bar_index=50,
        era="2023_2026" if group == GROUP_LATEST else "2015_2019",
        comparison_group=group,
        trend_direction="UP",
        trend_state=trend_state,
        trend_strength=trend_strength,
        trend_confidence=0.7,
        structural_pattern=structural_pattern,
        close_position=close_position,
        volume_class="LOW",
        previous_volume_class="VERY_LOW",
        volume_class_relation="HIGHER_CLASS",
        spread_class="NARROW",
        spread_ratio=0.8,
        spread_percentile=20.0,
        volume_ratio=volume_ratio,
        volume_percentile=25.0,
        close_ratio=0.2,
        price_change_pct=-0.5,
        raw_volume_vs_previous_ratio=0.9,
        volume_class_delta=1.0,
    )


def _shift_frame() -> pd.DataFrame:
    rows = [
        _context(
            symbol="A.NS",
            session="2020-01-01T00:00:00",
            group=GROUP_PRIOR,
            trend_state="HEALTHY",
            structural_pattern="IMPROVING",
            close_position="LOWER",
            trend_strength=0.4,
            volume_ratio=0.5,
        ),
        _context(
            symbol="B.NS",
            session="2021-01-01T00:00:00",
            group=GROUP_PRIOR,
            trend_state="HEALTHY",
            structural_pattern="IMPROVING",
            close_position="ON_LOW",
            trend_strength=0.6,
            volume_ratio=0.7,
        ),
        _context(
            symbol="C.NS",
            session="2024-01-01T00:00:00",
            group=GROUP_LATEST,
            trend_state="CORRECTING",
            structural_pattern="STABLE",
            close_position="LOWER",
            trend_strength=0.8,
            volume_ratio=0.9,
        ),
        _context(
            symbol="D.NS",
            session="2025-01-01T00:00:00",
            group=GROUP_LATEST,
            trend_state="CORRECTING",
            structural_pattern="STABLE",
            close_position="LOWER",
            trend_strength=1.0,
            volume_ratio=1.1,
        ),
    ]
    return pd.DataFrame([asdict(row) for row in rows])


def test_continuous_shift_reports_latest_minus_prior() -> None:
    frame = _shift_frame()

    # Canonical builders hard-gate 263/42, so expand deterministic copies
    # while preserving the expected group means.
    prior = pd.concat([frame.iloc[[0, 1]]] * 132, ignore_index=True).iloc[:263]
    latest = pd.concat([frame.iloc[[2, 3]]] * 21, ignore_index=True)
    combined = pd.concat([prior, latest], ignore_index=True)

    rows = build_continuous_shift_rows(combined)
    strength = next(row for row in rows if row.feature == "trend_strength")

    assert strength.prior_count == 263
    assert strength.latest_count == 42
    assert strength.prior_mean == pytest.approx(
        prior["trend_strength"].mean()
    )
    assert strength.latest_mean == pytest.approx(0.9)
    assert strength.mean_delta > 0.0
    assert strength.standardized_mean_difference > 0.0


def test_categorical_shift_detects_state_distribution_change() -> None:
    frame = _shift_frame()
    prior = pd.concat([frame.iloc[[0, 1]]] * 132, ignore_index=True).iloc[:263]
    latest = pd.concat([frame.iloc[[2, 3]]] * 21, ignore_index=True)
    combined = pd.concat([prior, latest], ignore_index=True)

    rows = build_categorical_shift_rows(combined)

    correcting = next(
        row
        for row in rows
        if row.dimension == "trend_state"
        and row.level == "CORRECTING"
    )
    healthy = next(
        row
        for row in rows
        if row.dimension == "trend_state"
        and row.level == "HEALTHY"
    )

    assert correcting.prior_count == 0
    assert correcting.latest_count == 42
    assert correcting.latest_minus_prior_rate_pp == pytest.approx(100.0)

    assert healthy.prior_count == 263
    assert healthy.latest_count == 0
    assert healthy.latest_minus_prior_rate_pp == pytest.approx(-100.0)


def test_context_outcomes_group_by_exact_context_identity() -> None:
    contexts = pd.DataFrame(
        [
            asdict(
                _context(
                    symbol="A.NS",
                    session="2024-01-01T00:00:00",
                    group=GROUP_LATEST,
                    trend_state="HEALTHY",
                    structural_pattern="IMPROVING",
                    close_position="LOWER",
                    trend_strength=0.8,
                    volume_ratio=0.9,
                )
            ),
            asdict(
                _context(
                    symbol="B.NS",
                    session="2024-01-02T00:00:00",
                    group=GROUP_LATEST,
                    trend_state="CORRECTING",
                    structural_pattern="STABLE",
                    close_position="ON_LOW",
                    trend_strength=0.7,
                    volume_ratio=0.8,
                )
            ),
        ]
    )
    pairs = pd.DataFrame(
        [
            {
                "symbol": "A.NS",
                "target_session": "2024-01-01T00:00:00",
                "horizon_sessions": 1,
                "paired_return_delta_pct": 1.0,
                "paired_mfe_delta_pct": 2.0,
                "clean_pair": True,
            },
            {
                "symbol": "A.NS",
                "target_session": "2024-01-01T00:00:00",
                "horizon_sessions": 3,
                "paired_return_delta_pct": 3.0,
                "paired_mfe_delta_pct": 4.0,
                "clean_pair": True,
            },
            {
                "symbol": "B.NS",
                "target_session": "2024-01-02T00:00:00",
                "horizon_sessions": 1,
                "paired_return_delta_pct": -1.0,
                "paired_mfe_delta_pct": -2.0,
                "clean_pair": True,
            },
            {
                "symbol": "B.NS",
                "target_session": "2024-01-02T00:00:00",
                "horizon_sessions": 3,
                "paired_return_delta_pct": -3.0,
                "paired_mfe_delta_pct": -4.0,
                "clean_pair": True,
            },
        ]
    )

    rows = build_context_outcome_rows(
        contexts=contexts,
        pair_outcomes=pairs,
        horizons=(1, 3),
    )

    healthy_h1 = next(
        row
        for row in rows
        if row.dimension == "trend_state"
        and row.level == "HEALTHY"
        and row.horizon_sessions == 1
    )
    correcting_h3 = next(
        row
        for row in rows
        if row.dimension == "trend_state"
        and row.level == "CORRECTING"
        and row.horizon_sessions == 3
    )

    assert healthy_h1.source_target_count == 1
    assert healthy_h1.event_weighted_mfe_delta_pct == pytest.approx(2.0)
    assert healthy_h1.symbol_normalized_return_delta_pct == pytest.approx(1.0)

    assert correcting_h3.source_target_count == 1
    assert correcting_h3.event_weighted_return_delta_pct == pytest.approx(-3.0)
    assert correcting_h3.symbol_normalized_mfe_delta_pct == pytest.approx(-4.0)

    higher_h1 = next(
        row
        for row in rows
        if row.dimension == "volume_class_relation"
        and row.level == "HIGHER_CLASS"
        and row.horizon_sessions == 1
    )
    assert higher_h1.source_target_count == 2
    assert higher_h1.event_weighted_return_delta_pct == pytest.approx(0.0)


def test_context_outcomes_ignore_nonclean_pairs() -> None:
    contexts = pd.DataFrame(
        [
            asdict(
                _context(
                    symbol="A.NS",
                    session="2024-01-01T00:00:00",
                    group=GROUP_LATEST,
                    trend_state="HEALTHY",
                    structural_pattern="IMPROVING",
                    close_position="LOWER",
                    trend_strength=0.8,
                    volume_ratio=0.9,
                )
            )
        ]
    )
    pairs = pd.DataFrame(
        [
            {
                "symbol": "A.NS",
                "target_session": "2024-01-01T00:00:00",
                "horizon_sessions": 1,
                "paired_return_delta_pct": 99.0,
                "paired_mfe_delta_pct": 99.0,
                "clean_pair": False,
            }
        ]
    )

    rows = build_context_outcome_rows(
        contexts=contexts,
        pair_outcomes=pairs,
        horizons=(1,),
    )
    assert rows == ()
