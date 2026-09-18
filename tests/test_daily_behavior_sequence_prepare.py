from __future__ import annotations

from dataclasses import replace

import pandas as pd
import pytest

import audit.daily_behavior_sequence_prepare as prepare_module
from audit.daily_behavior_sequence_dataset import (
    load_daily_behavior_sequence_dataset,
)
from audit.daily_behavior_sequence_prepare import (
    DAILY_SEQUENCE_COMPOSER_ID,
    DAILY_SEQUENCE_COMPOSER_SOURCE_KIND,
    prepare_daily_behavior_sequence_case,
    write_prepared_daily_behavior_sequence_case,
)
from audit.daily_behavior_sequence_runner import (
    run_daily_behavior_sequence_historical_study,
)
from background.qualification import PatternQualification
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection
from weekly_setup import (
    WeeklySetup,
    WeeklySetupDirection,
    build_weekly_setup_id,
)


def _daily(periods: int = 30) -> pd.DataFrame:
    index = pd.bdate_range("2026-08-03", periods=periods)
    values = [100.0 + index for index in range(periods)]
    return pd.DataFrame(
        {
            "open": values,
            "high": [value + 2.0 for value in values],
            "low": [value - 1.0 for value in values],
            "close": [value + 1.0 for value in values],
            "volume": [1000.0 + index * 10.0 for index in range(periods)],
        },
        index=index,
    )


def _setup(
    *,
    signal_week: str = "2026-08-03",
    direction: WeeklySetupDirection = WeeklySetupDirection.BULLISH,
) -> WeeklySetup:
    qualification = (
        PatternQualification.PERSISTENT_BULLISH
        if direction is WeeklySetupDirection.BULLISH
        else PatternQualification.PERSISTENT_BEARISH
    )
    return WeeklySetup(
        setup_id=build_weekly_setup_id("LT.NS", signal_week, direction),
        symbol="LT.NS",
        direction=direction,
        signal_week=signal_week,
        qualification=qualification,
        weekly_confidence=0.8,
        weekly_net_strength=0.6,
        weekly_net_pressure=0.4,
    )


def _prefix_evaluator(prefix: pd.DataFrame) -> tuple[Evidence, ...]:
    target = len(prefix) - 1
    if target not in {20, 22, 25}:
        return ()
    session = pd.Timestamp(prefix.index[-1]).isoformat()
    return (
        Evidence(
            code=EvidenceCode.DEMAND_COMING_IN,
            category=EvidenceCategory.SIGNAL,
            direction=EvidenceDirection.BULLISH,
            strength=0.8,
            weight=1.0,
            observation="synthetic integration evidence",
            description="synthetic integration evidence",
            bar_index=target,
            week_beginning=session,
            quality=0.9,
        ),
    )


def _prepare(**overrides):
    values = {
        "dataset_id": "k7-integration-case-01",
        "symbol": "lt.ns",
        "daily": _daily(),
        "weekly_setups": (_setup(),),
        "source_reference": "test-fixture:daily-ohlcv",
        "prepared_at_utc": "2026-09-18T13:30:00Z",
        "now": "2026-09-18T16:00:00+05:30",
        "min_target_index": 20,
        "prefix_evaluator": _prefix_evaluator,
    }
    values.update(overrides)
    return prepare_daily_behavior_sequence_case(**values)


def test_composer_builds_one_frozen_k4_input_from_k5_and_k6() -> None:
    case = _prepare()
    study_input = case.study_input

    assert case.symbol == "LT.NS"
    assert case.composer_id == DAILY_SEQUENCE_COMPOSER_ID
    assert case.dataset.source.kind == DAILY_SEQUENCE_COMPOSER_SOURCE_KIND
    assert case.dataset.symbols == ("LT.NS",)
    assert case.is_actionable is False
    assert case.dataset.is_actionable is False

    assert study_input.bars.index.equals(case.evidence_archive.completed_daily.index)
    assert list(study_input.bars.columns) == ["close", "high", "low"]
    assert study_input.weekly_directions == case.weekly_direction_archive.assignments
    assert study_input.evidence == case.evidence_archive.evidence
    assert len(study_input.evidence) == 3


def test_composer_embeds_both_source_fingerprints_in_k4_provenance() -> None:
    case = _prepare(notes="first causal integration fixture")

    notes = case.dataset.source.notes
    assert f"composer={DAILY_SEQUENCE_COMPOSER_ID}" in notes
    assert case.daily_source_fingerprint.sha256 in notes
    assert case.weekly_source_fingerprint.sha256 in notes
    assert "first causal integration fixture" in notes


def test_forming_daily_bar_is_excluded_identically_by_k5_and_k6() -> None:
    daily = _daily()
    last = pd.Timestamp(daily.index[-1])
    now = last.tz_localize("Asia/Kolkata") + pd.Timedelta(hours=12)

    case = _prepare(daily=daily, now=now)

    assert len(case.evidence_archive.completed_daily) == len(daily) - 1
    assert len(case.weekly_direction_archive.completed_daily) == len(daily) - 1
    assert case.study_input.bars.index[-1] == daily.index[-2]


def test_same_week_setup_cannot_leak_into_its_own_daily_sessions() -> None:
    setup = _setup(signal_week="2026-08-31")
    case = _prepare(weekly_setups=(setup,))

    assigned = {
        item.bar_index: item.direction
        for item in case.study_input.weekly_directions
    }
    sessions = list(case.study_input.bars.index)

    same_week_indices = [
        index
        for index, session in enumerate(sessions)
        if pd.Timestamp("2026-08-31") <= session <= pd.Timestamp("2026-09-04")
    ]
    assert same_week_indices
    assert all(index not in assigned for index in same_week_indices)

    first_after = sessions.index(pd.Timestamp("2026-09-07"))
    assert assigned[first_after] is WeeklySetupDirection.BULLISH


def test_future_extension_preserves_existing_evidence_and_directions() -> None:
    base_daily = _daily(26)
    extended_daily = _daily(30)

    base = _prepare(
        daily=base_daily,
        now="2026-09-07T16:00:00+05:30",
    )
    extended = _prepare(
        daily=extended_daily,
        now="2026-09-18T16:00:00+05:30",
    )

    base_bar_count = len(base.study_input.bars)
    assert extended.study_input.bars.iloc[:base_bar_count].equals(
        base.study_input.bars
    )
    assert tuple(
        item
        for item in extended.study_input.evidence
        if item.bar_index < base_bar_count
    ) == base.study_input.evidence
    assert tuple(
        item
        for item in extended.study_input.weekly_directions
        if item.bar_index < base_bar_count
    ) == base.study_input.weekly_directions


def test_composer_fails_closed_if_k5_k6_completed_sessions_diverge(
    monkeypatch,
) -> None:
    original = prepare_module.produce_causal_weekly_direction_assignments

    def mismatched_weekly_archive(**kwargs):
        archive = original(**kwargs)
        return replace(
            archive,
            completed_daily=archive.completed_daily.iloc[:-1].copy(),
        )

    monkeypatch.setattr(
        prepare_module,
        "produce_causal_weekly_direction_assignments",
        mismatched_weekly_archive,
    )

    with pytest.raises(ValueError, match="completed daily session mismatch"):
        _prepare()


def test_written_case_round_trips_through_k4_and_runs_through_k3(
    tmp_path,
) -> None:
    case = _prepare()
    path = write_prepared_daily_behavior_sequence_case(
        case,
        tmp_path / "first-case.json",
    )
    loaded = load_daily_behavior_sequence_dataset(path)

    assert loaded.fingerprints == case.dataset.fingerprints
    assert loaded.source == case.dataset.source

    study = run_daily_behavior_sequence_historical_study(
        loaded.inputs,
        horizons_bars=(1, 2),
        lookback_bars=5,
        expected_fingerprints=loaded.fingerprints,
    )

    assert study.successful_symbols == ("LT.NS",)
    assert study.failed_symbols == ()
    assert study.external_baseline_used is True
    assert study.is_actionable is False


def test_blank_source_reference_fails_through_existing_k4_contract() -> None:
    with pytest.raises(ValueError, match="source.reference"):
        _prepare(source_reference=" ")
