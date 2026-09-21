from __future__ import annotations

import pandas as pd
import pytest

from audit.daily_event_no_supply_forward_outcomes import (
    COHORT_ALTERNATE,
    COHORT_CURRENT,
    NoSupplyForwardEventOutcome,
    build_forward_outcome_summaries,
    calculate_symbol_forward_outcomes,
    l6_equivalent_session_frame,
    normalize_forward_horizons,
)


def _daily() -> pd.DataFrame:
    index = pd.bdate_range("2026-01-01", periods=8)
    return pd.DataFrame(
        {
            "open": [99, 101, 101, 103, 102, 106, 105, 108],
            "high": [101, 103, 104, 105, 106, 108, 109, 111],
            "low": [98, 99, 100, 101, 101, 104, 103, 106],
            "close": [100, 100, 102, 104, 103, 107, 106, 110],
            "volume": [1000] * 8,
        },
        index=index,
    )


def _events() -> pd.DataFrame:
    daily = _daily()
    return pd.DataFrame(
        [
            {
                "symbol": "AAA.NS",
                "bar_index": 1,
                "session": daily.index[1].isoformat(),
                "trend_direction": "DOWN",
                "cohort": COHORT_CURRENT,
            },
            {
                "symbol": "AAA.NS",
                "bar_index": 6,
                "session": daily.index[6].isoformat(),
                "trend_direction": "DOWN",
                "cohort": COHORT_CURRENT,
            },
            {
                "symbol": "AAA.NS",
                "bar_index": 2,
                "session": daily.index[2].isoformat(),
                "trend_direction": "UP",
                "cohort": COHORT_ALTERNATE,
            },
        ]
    )


def test_normalize_forward_horizons_is_sorted_unique() -> None:
    assert normalize_forward_horizons((5, 1, 3, 1)) == (1, 3, 5)
    with pytest.raises(ValueError, match="positive"):
        normalize_forward_horizons((0, 1))


def test_l6_session_frame_excludes_raw_weekend_rows() -> None:
    index = pd.DatetimeIndex(
        [
            "2026-01-02",
            "2026-01-03",  # Saturday raw/special-session row.
            "2026-01-05",
            "2026-01-06",
            "2026-01-07",
        ]
    )
    daily = pd.DataFrame(
        {
            "open": [100, 101, 102, 103, 104],
            "high": [102, 103, 104, 105, 106],
            "low": [99, 100, 101, 102, 103],
            "close": [101, 102, 103, 104, 105],
            "volume": [1000] * 5,
        },
        index=index,
    )

    filtered = l6_equivalent_session_frame(daily)
    assert list(filtered.index) == [
        pd.Timestamp("2026-01-02"),
        pd.Timestamp("2026-01-05"),
        pd.Timestamp("2026-01-06"),
        pd.Timestamp("2026-01-07"),
    ]

    events = pd.DataFrame(
        [
            {
                "symbol": "AAA.NS",
                # Raw position is 3; canonical L6 position is 2 because
                # the Saturday row is not a default NSE session.
                "bar_index": 2,
                "session": pd.Timestamp("2026-01-06").isoformat(),
                "trend_direction": "DOWN",
                "cohort": COHORT_CURRENT,
            }
        ]
    )
    outcomes, censoring = calculate_symbol_forward_outcomes(
        symbol="AAA.NS",
        daily=daily,
        events=events,
        horizons=(1,),
    )

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.bar_index == 2
    assert outcome.horizon_session == pd.Timestamp(
        "2026-01-07"
    ).isoformat()
    assert outcome.event_close == 104.0
    assert outcome.horizon_close == 105.0

    current = next(
        item
        for item in censoring
        if item.cohort == COHORT_CURRENT
    )
    assert current.complete_event_count == 1
    assert current.censored_event_count == 0


def test_forward_outcomes_use_only_post_event_sessions() -> None:
    outcomes, censoring = calculate_symbol_forward_outcomes(
        symbol="AAA.NS",
        daily=_daily(),
        events=_events(),
        horizons=(1, 3),
    )

    current_h1 = next(
        item
        for item in outcomes
        if item.cohort == COHORT_CURRENT
        and item.bar_index == 1
        and item.horizon_sessions == 1
    )
    assert current_h1.horizon_session == _daily().index[2].isoformat()
    assert current_h1.event_close == 100.0
    assert current_h1.horizon_close == 102.0
    assert current_h1.forward_close_return_pct == pytest.approx(2.0)
    assert current_h1.max_favorable_excursion_pct == pytest.approx(4.0)
    assert current_h1.max_adverse_excursion_pct == pytest.approx(0.0)
    assert current_h1.positive_close is True

    current_h3 = next(
        item
        for item in outcomes
        if item.cohort == COHORT_CURRENT
        and item.bar_index == 1
        and item.horizon_sessions == 3
    )
    assert current_h3.horizon_close == 103.0
    assert current_h3.forward_close_return_pct == pytest.approx(3.0)
    assert current_h3.max_favorable_excursion_pct == pytest.approx(6.0)
    assert current_h3.max_adverse_excursion_pct == pytest.approx(0.0)

    late_current = [
        item
        for item in outcomes
        if item.cohort == COHORT_CURRENT
        and item.bar_index == 6
    ]
    assert [item.horizon_sessions for item in late_current] == [1]

    by_key = {
        (item.cohort, item.horizon_sessions): item
        for item in censoring
    }
    assert by_key[(COHORT_CURRENT, 1)].source_event_count == 2
    assert by_key[(COHORT_CURRENT, 1)].complete_event_count == 2
    assert by_key[(COHORT_CURRENT, 1)].censored_event_count == 0

    assert by_key[(COHORT_CURRENT, 3)].source_event_count == 2
    assert by_key[(COHORT_CURRENT, 3)].complete_event_count == 1
    assert by_key[(COHORT_CURRENT, 3)].censored_event_count == 1
    assert by_key[(COHORT_CURRENT, 3)].censoring_rate == 0.5

    assert by_key[(COHORT_ALTERNATE, 3)].complete_event_count == 1
    assert by_key[(COHORT_ALTERNATE, 3)].censored_event_count == 0


def test_forward_outcome_rejects_bar_index_drift() -> None:
    events = _events()
    events.loc[0, "bar_index"] = 99

    with pytest.raises(ValueError, match="bar index drift"):
        calculate_symbol_forward_outcomes(
            symbol="AAA.NS",
            daily=_daily(),
            events=events,
            horizons=(1,),
        )


def test_forward_outcome_flags_single_session_price_discontinuity() -> None:
    index = pd.bdate_range("2026-01-01", periods=5)
    daily = pd.DataFrame(
        {
            "open": [100.0, 101.0, 102.0, 250.0, 104.0],
            "high": [102.0, 103.0, 104.0, 255.0, 106.0],
            "low": [99.0, 100.0, 101.0, 245.0, 103.0],
            "close": [101.0, 102.0, 103.0, 250.0, 105.0],
            "volume": [1000] * 5,
        },
        index=index,
    )
    events = pd.DataFrame(
        [
            {
                "symbol": "AAA.NS",
                "bar_index": 1,
                "session": index[1].isoformat(),
                "trend_direction": "UP",
                "cohort": COHORT_ALTERNATE,
            }
        ]
    )

    outcomes, _ = calculate_symbol_forward_outcomes(
        symbol="AAA.NS",
        daily=daily,
        events=events,
        horizons=(2,),
        price_discontinuity_ratio=0.35,
    )

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.max_single_session_price_move_pct > 100.0
    assert outcome.price_discontinuity_in_event_or_window is True

def test_cohort_comparison_includes_event_and_symbol_normalized_views() -> None:
    outcomes = (
        NoSupplyForwardEventOutcome(
            symbol="AAA.NS",
            session="2026-01-01T00:00:00",
            bar_index=0,
            cohort=COHORT_CURRENT,
            trend_direction="DOWN",
            horizon_sessions=5,
            horizon_session="2026-01-08T00:00:00",
            event_close=100.0,
            horizon_close=110.0,
            forward_close_return_pct=10.0,
            max_favorable_excursion_pct=12.0,
            max_adverse_excursion_pct=-2.0,
            positive_close=True,
            max_single_session_price_move_pct=10.0,
            price_discontinuity_in_event_or_window=False,
        ),
        NoSupplyForwardEventOutcome(
            symbol="AAA.NS",
            session="2026-01-02T00:00:00",
            bar_index=1,
            cohort=COHORT_CURRENT,
            trend_direction="DOWN",
            horizon_sessions=5,
            horizon_session="2026-01-08T00:00:00",
            event_close=100.0,
            horizon_close=110.0,
            forward_close_return_pct=10.0,
            max_favorable_excursion_pct=11.0,
            max_adverse_excursion_pct=-3.0,
            positive_close=True,
            max_single_session_price_move_pct=10.0,
            price_discontinuity_in_event_or_window=False,
        ),
        NoSupplyForwardEventOutcome(
            symbol="BBB.NS",
            session="2026-01-01T00:00:00",
            bar_index=0,
            cohort=COHORT_CURRENT,
            trend_direction="DOWN",
            horizon_sessions=5,
            horizon_session="2026-01-08T00:00:00",
            event_close=100.0,
            horizon_close=90.0,
            forward_close_return_pct=-10.0,
            max_favorable_excursion_pct=1.0,
            max_adverse_excursion_pct=-12.0,
            positive_close=False,
            max_single_session_price_move_pct=10.0,
            price_discontinuity_in_event_or_window=False,
        ),
        NoSupplyForwardEventOutcome(
            symbol="AAA.NS",
            session="2026-01-03T00:00:00",
            bar_index=2,
            cohort=COHORT_ALTERNATE,
            trend_direction="UP",
            horizon_sessions=5,
            horizon_session="2026-01-08T00:00:00",
            event_close=100.0,
            horizon_close=105.0,
            forward_close_return_pct=5.0,
            max_favorable_excursion_pct=8.0,
            max_adverse_excursion_pct=-1.0,
            positive_close=True,
            max_single_session_price_move_pct=10.0,
            price_discontinuity_in_event_or_window=False,
        ),
        NoSupplyForwardEventOutcome(
            symbol="BBB.NS",
            session="2026-01-03T00:00:00",
            bar_index=2,
            cohort=COHORT_ALTERNATE,
            trend_direction="UP",
            horizon_sessions=5,
            horizon_session="2026-01-08T00:00:00",
            event_close=100.0,
            horizon_close=105.0,
            forward_close_return_pct=5.0,
            max_favorable_excursion_pct=7.0,
            max_adverse_excursion_pct=-2.0,
            positive_close=True,
            max_single_session_price_move_pct=10.0,
            price_discontinuity_in_event_or_window=False,
        ),
    )

    cohort_rows, symbol_rows, comparisons, quality_rows = (
        build_forward_outcome_summaries(
            outcomes,
            horizons=(5,),
        )
    )

    assert len(cohort_rows) == 2
    assert len(symbol_rows) == 4
    assert len(quality_rows) == 2
    row = comparisons[0]
    assert row.current_event_count == 3
    assert row.alternate_event_count == 2
    assert row.current_mean_close_return_pct == pytest.approx(
        10.0 / 3.0
    )
    assert row.alternate_mean_close_return_pct == 5.0

    # Current event-weighting is pulled upward by two AAA events, while
    # symbol-normalization gives AAA and BBB equal weight: (10 + -10) / 2.
    assert row.current_symbol_normalized_mean_return_pct == 0.0
    assert row.alternate_symbol_normalized_mean_return_pct == 5.0
    assert (
        row.alternate_minus_current_symbol_normalized_return_pct
        == 5.0
    )
    assert row.current_price_discontinuity_event_count == 0
    assert row.alternate_price_discontinuity_event_count == 0
    assert row.current_clean_event_count == 3
    assert row.alternate_clean_event_count == 2
    assert row.current_clean_mean_close_return_pct == pytest.approx(
        10.0 / 3.0
    )
    assert row.alternate_clean_mean_close_return_pct == 5.0
