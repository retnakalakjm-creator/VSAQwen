"""Run a frozen K4 daily-sequence dataset through the unchanged K3/K2/K1 stack."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from audit.daily_behavior_sequence_dataset import (
    FrozenDailyBehaviorSequenceDataset,
    load_daily_behavior_sequence_dataset,
)
from audit.daily_behavior_sequence_runner import (
    DailyBehaviorSequenceHistoricalStudy,
    DailyBehaviorSequenceStudyBundlePaths,
    run_daily_behavior_sequence_historical_study,
    write_daily_behavior_sequence_study_bundle,
)


FROZEN_DAILY_SEQUENCE_STUDY_RUNNER_ID = "k4-k3-k2-k1-frozen-study-v1"


@dataclass(frozen=True, slots=True)
class FrozenDailySequenceStudyRun:
    dataset: FrozenDailyBehaviorSequenceDataset
    study: DailyBehaviorSequenceHistoricalStudy
    paths: DailyBehaviorSequenceStudyBundlePaths
    bullish_assignment_count: int
    bearish_assignment_count: int
    other_assignment_count: int

    @property
    def is_actionable(self) -> bool:
        return False


def _direction_counts(
    dataset: FrozenDailyBehaviorSequenceDataset,
) -> tuple[int, int, int]:
    values = Counter(
        assignment.direction.value
        for study_input in dataset.inputs
        for assignment in study_input.weekly_directions
    )
    bullish = values.get("bullish", 0)
    bearish = values.get("bearish", 0)
    other = sum(
        count
        for direction, count in values.items()
        if direction not in {"bullish", "bearish"}
    )
    return bullish, bearish, other


def run_frozen_daily_sequence_study(
    *,
    dataset_path: str | Path,
    output_dir: str | Path,
    horizons_bars: tuple[int, ...] = (1, 3, 5, 10, 15),
    lookback_bars: int = 5,
) -> FrozenDailySequenceStudyRun:
    """Load one K4 dataset, verify it, and run the existing K3/K2/K1 study."""

    dataset = load_daily_behavior_sequence_dataset(dataset_path)
    study = run_daily_behavior_sequence_historical_study(
        dataset.inputs,
        horizons_bars=horizons_bars,
        lookback_bars=lookback_bars,
        expected_fingerprints=dataset.fingerprints,
    )
    paths = write_daily_behavior_sequence_study_bundle(
        study,
        output_dir=output_dir,
    )
    bullish, bearish, other = _direction_counts(dataset)

    return FrozenDailySequenceStudyRun(
        dataset=dataset,
        study=study,
        paths=paths,
        bullish_assignment_count=bullish,
        bearish_assignment_count=bearish,
        other_assignment_count=other,
    )


__all__ = [
    "FROZEN_DAILY_SEQUENCE_STUDY_RUNNER_ID",
    "FrozenDailySequenceStudyRun",
    "run_frozen_daily_sequence_study",
]
