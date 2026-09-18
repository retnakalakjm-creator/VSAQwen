from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from audit.genuine_daily_sequence_case import (
    GENUINE_DAILY_SEQUENCE_GENERATOR_ID,
    derive_historical_production_weekly_setups,
    fingerprint_production_weekly_source,
    prepare_genuine_daily_behavior_sequence_case,
    write_genuine_daily_behavior_sequence_case,
)
from audit.daily_behavior_sequence_dataset import (
    load_daily_behavior_sequence_dataset,
)
from background.qualification import PatternQualification
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection
from weekly_setup import WeeklySetupDirection


def _daily(periods: int = 80) -> pd.DataFrame:
    index = pd.bdate_range("2026-05-04", periods=periods)
    values = [100.0 + index * 0.5 for index in range(periods)]
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


def _candidate(
    *,
    week: str,
    qualification: PatternQualification = PatternQualification.PERSISTENT_BULLISH,
    actionable: bool = True,
):
    return SimpleNamespace(
        actionable=actionable,
        qualification=qualification,
        week=week,
        confidence=0.82,
        net_strength=1.1,
        net_pressure=0.7,
        qualifying_evidence=(),
        scoring_evidence=(),
    )


class _FakeMetrics:
    def calculate(self, frame: pd.DataFrame) -> pd.DataFrame:
        return frame.copy()


class _FakeRunner:
    def __init__(self, candidates):
        self._candidates = list(candidates)

    def scan(self, metrics: pd.DataFrame):
        assert not metrics.empty
        return list(self._candidates)


def _prefix_evaluator(prefix: pd.DataFrame) -> tuple[Evidence, ...]:
    target = len(prefix) - 1
    if target not in {20, 25, 30}:
        return ()
    return (
        Evidence(
            code=EvidenceCode.DEMAND_COMING_IN,
            category=EvidenceCategory.SIGNAL,
            direction=EvidenceDirection.BULLISH,
            strength=0.8,
            weight=1.0,
            observation="integration evidence",
            description="integration evidence",
            bar_index=target,
            week_beginning=pd.Timestamp(prefix.index[-1]).isoformat(),
            quality=0.9,
        ),
    )


def test_weekly_archive_materializes_only_authoritative_actionable_candidates() -> None:
    runner = _FakeRunner(
        (
            _candidate(week="2026-05-04"),
            _candidate(
                week="2026-05-11",
                qualification=PatternQualification.UNQUALIFIED,
            ),
            _candidate(
                week="2026-05-18",
                actionable=False,
            ),
            _candidate(
                week="2026-05-25",
                qualification=PatternQualification.PERSISTENT_BEARISH,
            ),
        )
    )

    archive = derive_historical_production_weekly_setups(
        symbol="lt.ns",
        daily=_daily(),
        now="2026-09-18T16:00:00+05:30",
        historical_runner=runner,
        metrics_engine=_FakeMetrics(),
    )

    assert archive.symbol == "LT.NS"
    assert archive.candidate_count == 4
    assert archive.setup_count == 2
    assert tuple(setup.direction for setup in archive.setups) == (
        WeeklySetupDirection.BULLISH,
        WeeklySetupDirection.BEARISH,
    )
    assert archive.is_actionable is False


def test_weekly_source_fingerprint_changes_when_completed_weekly_ohlcv_changes() -> None:
    daily = _daily()
    archive = derive_historical_production_weekly_setups(
        symbol="LT.NS",
        daily=daily,
        now="2026-09-18T16:00:00+05:30",
        historical_runner=_FakeRunner(()),
        metrics_engine=_FakeMetrics(),
    )

    first = archive.source_fingerprint
    changed_weekly = archive.completed_weekly.copy()
    changed_weekly.loc[
        changed_weekly.index[-1],
        "close",
    ] += 3.0
    changed = fingerprint_production_weekly_source(
        symbol="LT.NS",
        completed_weekly=changed_weekly,
    )

    assert first.sha256.startswith("sha256:")
    assert changed.sha256 != first.sha256


def test_genuine_case_composes_production_weekly_setups_with_k5_k6_k4() -> None:
    runner = _FakeRunner((_candidate(week="2026-05-04"),))

    case = prepare_genuine_daily_behavior_sequence_case(
        dataset_id="genuine-lt-case-01",
        symbol="LT.NS",
        daily=_daily(),
        source_reference="test-market-data-source",
        prepared_at_utc="2026-09-18T13:45:00Z",
        now="2026-09-18T16:00:00+05:30",
        prefix_evaluator=_prefix_evaluator,
        historical_runner=runner,
        metrics_engine=_FakeMetrics(),
    )

    assert case.generator_id == GENUINE_DAILY_SEQUENCE_GENERATOR_ID
    assert case.weekly_archive.setup_count == 1
    assert case.dataset.symbols == ("LT.NS",)
    assert case.dataset.is_actionable is False
    assert case.is_actionable is False
    assert case.study_input.weekly_directions
    assert case.study_input.evidence

    notes = case.dataset.source.notes
    assert case.weekly_archive.source_fingerprint.sha256 in notes
    assert "production_weekly_candidate_count=1" in notes
    assert "production_weekly_setup_count=1" in notes


def test_genuine_case_fails_closed_when_production_history_has_no_setup() -> None:
    with pytest.raises(ValueError, match="no actionable production weekly setups"):
        prepare_genuine_daily_behavior_sequence_case(
            dataset_id="empty-weekly-case",
            symbol="LT.NS",
            daily=_daily(),
            source_reference="test-market-data-source",
            prepared_at_utc="2026-09-18T13:45:00Z",
            now="2026-09-18T16:00:00+05:30",
            prefix_evaluator=_prefix_evaluator,
            historical_runner=_FakeRunner(()),
            metrics_engine=_FakeMetrics(),
        )


def test_written_genuine_case_round_trips_through_existing_k4_contract(
    tmp_path,
) -> None:
    case = prepare_genuine_daily_behavior_sequence_case(
        dataset_id="genuine-lt-case-01",
        symbol="LT.NS",
        daily=_daily(),
        source_reference="test-market-data-source",
        prepared_at_utc="2026-09-18T13:45:00Z",
        now="2026-09-18T16:00:00+05:30",
        prefix_evaluator=_prefix_evaluator,
        historical_runner=_FakeRunner((_candidate(week="2026-05-04"),)),
        metrics_engine=_FakeMetrics(),
    )

    path = write_genuine_daily_behavior_sequence_case(
        case,
        tmp_path / "genuine.json",
    )
    loaded = load_daily_behavior_sequence_dataset(path)

    assert loaded.fingerprints == case.dataset.fingerprints
    assert loaded.source == case.dataset.source
    assert loaded.is_actionable is False
