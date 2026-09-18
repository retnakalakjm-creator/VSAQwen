from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from audit.daily_behavior_sequence_dataset import (
    DailyBehaviorSequenceDatasetSource,
    freeze_daily_behavior_sequence_dataset,
    write_daily_behavior_sequence_dataset,
)
from audit.daily_behavior_sequence_runner import (
    DailyBehaviorSequenceDirectionAssignment,
    DailyBehaviorSequenceStudyInput,
)
from audit.frozen_daily_sequence_study import (
    FROZEN_DAILY_SEQUENCE_STUDY_RUNNER_ID,
    run_frozen_daily_sequence_study,
)
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection
from weekly_setup import WeeklySetupDirection


def _input() -> DailyBehaviorSequenceStudyInput:
    bars = pd.DataFrame(
        {
            "close": [100.0, 101.0, 102.0, 104.0, 103.0, 106.0, 108.0],
            "high": [101.0, 102.0, 103.0, 105.0, 104.0, 107.0, 109.0],
            "low": [99.0, 100.0, 101.0, 103.0, 102.0, 105.0, 107.0],
        },
        index=pd.date_range("2026-09-01", periods=7, freq="D"),
    )
    evidence = (
        Evidence(
            code=EvidenceCode.DEMAND_COMING_IN,
            category=EvidenceCategory.SIGNAL,
            direction=EvidenceDirection.BULLISH,
            strength=0.8,
            weight=1.0,
            observation="daily demand",
            description="daily demand",
            bar_index=2,
            week_beginning="2026-09-03T00:00:00",
            quality=0.9,
        ),
        Evidence(
            code=EvidenceCode.INCREASING_SUPPLY,
            category=EvidenceCategory.SIGNAL,
            direction=EvidenceDirection.BEARISH,
            strength=0.7,
            weight=1.0,
            observation="daily supply",
            description="daily supply",
            bar_index=4,
            week_beginning="2026-09-05T00:00:00",
            quality=0.8,
        ),
    )
    directions = (
        DailyBehaviorSequenceDirectionAssignment(
            bar_index=2,
            direction=WeeklySetupDirection.BULLISH,
        ),
        DailyBehaviorSequenceDirectionAssignment(
            bar_index=4,
            direction=WeeklySetupDirection.BEARISH,
        ),
    )
    return DailyBehaviorSequenceStudyInput(
        symbol="AAA.NS",
        bars=bars,
        weekly_directions=directions,
        evidence=evidence,
    )


def _write_dataset(tmp_path):
    source = DailyBehaviorSequenceDatasetSource(
        kind="test",
        reference="fixture:test",
        prepared_at_utc="2026-09-18T14:00:00Z",
    )
    dataset = freeze_daily_behavior_sequence_dataset(
        dataset_id="frozen-study-test",
        source=source,
        inputs=(_input(),),
    )
    path = tmp_path / "dataset.json"
    write_daily_behavior_sequence_dataset(dataset, path)
    return dataset, path


def test_runner_loads_k4_and_writes_existing_k3_bundle(tmp_path) -> None:
    dataset, path = _write_dataset(tmp_path)

    result = run_frozen_daily_sequence_study(
        dataset_path=path,
        output_dir=tmp_path / "study",
        horizons_bars=(1, 2),
        lookback_bars=3,
    )

    assert result.dataset.fingerprints == dataset.fingerprints
    assert result.study.successful_symbols == ("AAA.NS",)
    assert result.study.failed_symbols == ()
    assert result.study.external_baseline_used is True
    assert result.study.is_actionable is False
    assert result.is_actionable is False
    assert result.bullish_assignment_count == 1
    assert result.bearish_assignment_count == 1
    assert result.other_assignment_count == 0

    for output in result.paths.as_dict().values():
        assert (tmp_path / "study" / Path(output).name).exists()


def test_runner_bundle_remains_explicitly_non_actionable(tmp_path) -> None:
    _, path = _write_dataset(tmp_path)
    result = run_frozen_daily_sequence_study(
        dataset_path=path,
        output_dir=tmp_path / "study",
        horizons_bars=(1,),
    )

    payload = json.loads(result.paths.summary_json.read_text(encoding="utf-8"))
    assert payload["external_baseline_used"] is True
    assert payload["is_actionable"] is False


def test_runner_refuses_tampered_frozen_dataset(tmp_path) -> None:
    _, path = _write_dataset(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["symbols"][0]["bars"][0]["close"] = 999.0
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="fingerprint mismatch"):
        run_frozen_daily_sequence_study(
            dataset_path=path,
            output_dir=tmp_path / "study",
        )


def test_runner_id_is_stable() -> None:
    assert FROZEN_DAILY_SEQUENCE_STUDY_RUNNER_ID == (
        "k4-k3-k2-k1-frozen-study-v1"
    )
