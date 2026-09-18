import json

import pandas as pd

from audit.daily_behavior_sequence_runner import (
    DailyBehaviorSequenceDirectionAssignment,
    DailyBehaviorSequenceStudyInput,
    fingerprint_daily_behavior_sequence_input,
    run_daily_behavior_sequence_historical_study,
    run_daily_behavior_sequence_symbol_study,
    write_daily_behavior_sequence_study_bundle,
)
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection
from weekly_setup import WeeklySetupDirection


def _bars(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "close": values,
            "high": [value + 1.0 for value in values],
            "low": [value - 1.0 for value in values],
        },
        index=pd.date_range("2026-01-01", periods=len(values), freq="D"),
    )


def _evidence(
    code: EvidenceCode,
    direction: EvidenceDirection,
    bar_index: int,
) -> Evidence:
    return Evidence(
        code=code,
        category=EvidenceCategory.SIGNAL,
        direction=direction,
        strength=0.8,
        weight=1.0,
        observation=str(code),
        description=str(code),
        bar_index=bar_index,
        week_beginning="2026-01-01",
    )


def _bullish_input(symbol: str = "AAA.NS") -> DailyBehaviorSequenceStudyInput:
    return DailyBehaviorSequenceStudyInput(
        symbol=symbol,
        bars=_bars([100.0, 101.0, 102.0, 104.0, 107.0, 109.0, 111.0]),
        weekly_directions=(
            DailyBehaviorSequenceDirectionAssignment(
                bar_index=2,
                direction=WeeklySetupDirection.BULLISH,
            ),
            DailyBehaviorSequenceDirectionAssignment(
                bar_index=4,
                direction=WeeklySetupDirection.BULLISH,
            ),
        ),
        evidence=(
            _evidence(
                EvidenceCode.NO_SUPPLY,
                EvidenceDirection.BULLISH,
                1,
            ),
            _evidence(
                EvidenceCode.DEMAND_COMING_IN,
                EvidenceDirection.BULLISH,
                2,
            ),
            _evidence(
                EvidenceCode.ABSORPTION,
                EvidenceDirection.BULLISH,
                4,
            ),
        ),
    )


def _bearish_input(symbol: str = "BBB.NS") -> DailyBehaviorSequenceStudyInput:
    return DailyBehaviorSequenceStudyInput(
        symbol=symbol,
        bars=_bars([120.0, 119.0, 118.0, 116.0, 113.0, 110.0, 108.0]),
        weekly_directions=(
            DailyBehaviorSequenceDirectionAssignment(
                bar_index=2,
                direction=WeeklySetupDirection.BEARISH,
            ),
        ),
        evidence=(
            _evidence(
                EvidenceCode.NO_DEMAND,
                EvidenceDirection.BEARISH,
                1,
            ),
            _evidence(
                EvidenceCode.SUPPLY_COMING_IN,
                EvidenceDirection.BEARISH,
                2,
            ),
        ),
    )


def test_input_fingerprint_is_deterministic_for_logically_equivalent_ordering() -> None:
    original = _bullish_input()
    reordered = DailyBehaviorSequenceStudyInput(
        symbol="aaa.ns",
        bars=original.bars.copy(),
        weekly_directions=tuple(reversed(original.weekly_directions)),
        evidence=tuple(reversed(original.evidence)),
    )

    first = fingerprint_daily_behavior_sequence_input(original)
    second = fingerprint_daily_behavior_sequence_input(reordered)

    assert first.symbol == "AAA.NS"
    assert first.sha256 == second.sha256
    assert first.bar_count == 7
    assert first.direction_assignment_count == 2
    assert first.evidence_count == 3


def test_input_fingerprint_changes_when_consumed_price_history_changes() -> None:
    original = _bullish_input()
    changed_bars = original.bars.copy()
    changed_bars.iloc[5, changed_bars.columns.get_loc("close")] += 5.0
    changed = DailyBehaviorSequenceStudyInput(
        symbol=original.symbol,
        bars=changed_bars,
        weekly_directions=original.weekly_directions,
        evidence=original.evidence,
    )

    assert (
        fingerprint_daily_behavior_sequence_input(original).sha256
        != fingerprint_daily_behavior_sequence_input(changed).sha256
    )


def test_symbol_study_replays_each_visible_weekly_direction_bar() -> None:
    result = run_daily_behavior_sequence_symbol_study(
        _bullish_input(),
        horizons_bars=(1, 2),
        lookback_bars=3,
    )

    assert result.symbol == "AAA.NS"
    assert tuple(item.bar_index for item in result.records) == (2, 4)
    assert result.fresh_sequence_count == 2
    assert result.outcome_observation_count == 4
    assert all(record.is_actionable is False for record in result.records)
    assert result.is_actionable is False


def test_multi_symbol_study_aggregates_without_ranking_sequences() -> None:
    study = run_daily_behavior_sequence_historical_study(
        (_bullish_input(), _bearish_input()),
        horizons_bars=(1, 2),
        lookback_bars=3,
    )

    assert study.requested_symbols == ("AAA.NS", "BBB.NS")
    assert study.successful_symbols == ("AAA.NS", "BBB.NS")
    assert study.failed_symbols == ()
    assert study.record_count == 3
    assert study.fresh_sequence_count == 3
    assert study.outcome_observation_count == 6
    assert len(study.input_fingerprints) == 2
    assert study.summaries
    assert all(item.is_actionable is False for item in study.summaries)
    assert study.is_actionable is False


def test_continue_on_symbol_error_records_exact_failure() -> None:
    good = _bullish_input()
    bad = DailyBehaviorSequenceStudyInput(
        symbol="BAD.NS",
        bars=_bars([10.0, 11.0, 12.0]),
        weekly_directions=(
            DailyBehaviorSequenceDirectionAssignment(
                bar_index=9,
                direction=WeeklySetupDirection.BULLISH,
            ),
        ),
        evidence=(),
    )

    study = run_daily_behavior_sequence_historical_study(
        (good, bad),
        horizons_bars=(1,),
        continue_on_symbol_error=True,
    )

    assert study.successful_symbols == ("AAA.NS",)
    assert study.failed_symbols == ("BAD.NS",)
    assert len(study.failures) == 1
    failure = study.failures[0]
    assert failure.stage == "study"
    assert failure.error_type == "IndexError"
    assert "bar_index" in failure.message


def test_expected_fingerprint_gate_rejects_changed_prepared_input() -> None:
    original = _bullish_input()
    expected = fingerprint_daily_behavior_sequence_input(original)

    changed_bars = original.bars.copy()
    changed_bars.iloc[3, changed_bars.columns.get_loc("high")] += 3.0
    changed = DailyBehaviorSequenceStudyInput(
        symbol=original.symbol,
        bars=changed_bars,
        weekly_directions=original.weekly_directions,
        evidence=original.evidence,
    )

    try:
        run_daily_behavior_sequence_historical_study(
            (changed,),
            horizons_bars=(1,),
            expected_fingerprints=(expected,),
        )
    except ValueError as exc:
        assert "fingerprint mismatch" in str(exc)
    else:
        raise AssertionError("changed input should fail the fingerprint gate")


def test_study_bundle_writes_reproducible_research_artifacts(tmp_path) -> None:
    study = run_daily_behavior_sequence_historical_study(
        (_bullish_input(), _bearish_input()),
        horizons_bars=(1,),
        lookback_bars=3,
    )

    paths = write_daily_behavior_sequence_study_bundle(study, tmp_path)

    assert paths.summary_json.exists()
    assert paths.input_fingerprints_json.exists()
    assert paths.input_fingerprints_csv.exists()
    assert paths.failures_csv.exists()
    assert paths.sequence_records_csv.exists()
    assert paths.outcomes_csv.exists()
    assert paths.summaries_csv.exists()

    summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    assert summary["requested_symbol_count"] == 2
    assert summary["successful_symbol_count"] == 2
    assert summary["failed_symbol_count"] == 0
    assert summary["fresh_sequence_count"] == 3
    assert summary["is_actionable"] is False

    fingerprints = json.loads(
        paths.input_fingerprints_json.read_text(encoding="utf-8")
    )
    assert fingerprints["symbols"] == ["AAA.NS", "BBB.NS"]
    assert len(fingerprints["fingerprints"]) == 2
    assert fingerprints["is_actionable"] is False

    records = pd.read_csv(paths.sequence_records_csv)
    outcomes = pd.read_csv(paths.outcomes_csv)
    summaries = pd.read_csv(paths.summaries_csv)

    assert len(records) == 3
    assert len(outcomes) == 3
    assert not summaries.empty
    assert records["is_actionable"].eq(False).all()
    assert outcomes["is_actionable"].eq(False).all()
    assert summaries["is_actionable"].eq(False).all()


def test_bundle_preserves_headers_when_no_sequence_records(tmp_path) -> None:
    empty_signal_input = DailyBehaviorSequenceStudyInput(
        symbol="EMPTY.NS",
        bars=_bars([10.0, 11.0, 12.0]),
        weekly_directions=(),
        evidence=(),
    )
    study = run_daily_behavior_sequence_historical_study(
        (empty_signal_input,),
        horizons_bars=(1,),
    )

    paths = write_daily_behavior_sequence_study_bundle(study, tmp_path)

    records = pd.read_csv(paths.sequence_records_csv)
    outcomes = pd.read_csv(paths.outcomes_csv)
    summaries = pd.read_csv(paths.summaries_csv)

    assert records.empty
    assert outcomes.empty
    assert summaries.empty
    assert "fresh_behavior" in records.columns
    assert "outcome_available" in outcomes.columns
    assert "complete_outcome_count" in summaries.columns
