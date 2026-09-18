import json

import pandas as pd
import pytest

from audit.daily_behavior_sequence_dataset import (
    DAILY_SEQUENCE_DATASET_SCHEMA_VERSION,
    DailyBehaviorSequenceDatasetSource,
    freeze_daily_behavior_sequence_dataset,
    load_daily_behavior_sequence_dataset,
    write_daily_behavior_sequence_dataset,
)
from audit.daily_behavior_sequence_runner import (
    DailyBehaviorSequenceDirectionAssignment,
    DailyBehaviorSequenceStudyInput,
    run_daily_behavior_sequence_historical_study,
)
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection
from weekly_setup import WeeklySetupDirection


def _bars() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "close": [100.0, 101.0, 103.0, 105.0, 108.0, 110.0],
            "high": [101.0, 102.0, 104.0, 106.0, 109.0, 111.0],
            "low": [99.0, 100.0, 102.0, 104.0, 107.0, 109.0],
        },
        index=pd.date_range("2026-07-01", periods=6, freq="D"),
    )


def _evidence(
    code: EvidenceCode,
    direction: EvidenceDirection,
    bar_index: int,
    *,
    test_index: int | None = None,
    recovery_index: int | None = None,
) -> Evidence:
    return Evidence(
        code=code,
        category=EvidenceCategory.SIGNAL,
        direction=direction,
        strength=0.8,
        weight=1.25,
        observation=f"observation-{code.value}",
        description=f"description-{code.value}",
        bar_index=bar_index,
        week_beginning="2026-07-01",
        test_index=test_index,
        recovery_index=recovery_index,
        quality=0.9,
    )


def _input() -> DailyBehaviorSequenceStudyInput:
    return DailyBehaviorSequenceStudyInput(
        symbol="LT.NS",
        bars=_bars(),
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
                test_index=0,
            ),
            _evidence(
                EvidenceCode.DEMAND_COMING_IN,
                EvidenceDirection.BULLISH,
                2,
                recovery_index=3,
            ),
            _evidence(
                EvidenceCode.ABSORPTION,
                EvidenceDirection.BULLISH,
                4,
            ),
        ),
    )


def _source() -> DailyBehaviorSequenceDatasetSource:
    return DailyBehaviorSequenceDatasetSource(
        kind="manual_daily_evidence_review",
        reference="casebook/LT.NS/2026-07",
        prepared_at_utc="2026-09-18T12:30:00Z",
        notes="Research-only prepared daily evidence.",
    )


def test_frozen_dataset_round_trip_preserves_k3_fingerprints(tmp_path) -> None:
    frozen = freeze_daily_behavior_sequence_dataset(
        dataset_id="k4-lt-daily-case-01",
        source=_source(),
        inputs=(_input(),),
    )
    path = write_daily_behavior_sequence_dataset(
        frozen,
        tmp_path / "dataset.json",
    )

    loaded = load_daily_behavior_sequence_dataset(path)

    assert loaded.schema_version == DAILY_SEQUENCE_DATASET_SCHEMA_VERSION
    assert loaded.dataset_id == "k4-lt-daily-case-01"
    assert loaded.price_timeframe == "1D"
    assert loaded.evidence_timeframe == "1D"
    assert loaded.source == _source()
    assert loaded.symbols == ("LT.NS",)
    assert loaded.fingerprints == frozen.fingerprints
    assert loaded.is_actionable is False

    original_evidence = frozen.inputs[0].evidence
    loaded_evidence = loaded.inputs[0].evidence
    assert loaded_evidence == original_evidence


def test_loaded_dataset_runs_directly_through_k3(tmp_path) -> None:
    frozen = freeze_daily_behavior_sequence_dataset(
        dataset_id="k4-lt-daily-case-01",
        source=_source(),
        inputs=(_input(),),
    )
    path = write_daily_behavior_sequence_dataset(
        frozen,
        tmp_path / "dataset.json",
    )
    loaded = load_daily_behavior_sequence_dataset(path)

    study = run_daily_behavior_sequence_historical_study(
        loaded.inputs,
        horizons_bars=(1, 2),
        lookback_bars=3,
        expected_fingerprints=loaded.fingerprints,
    )

    assert study.successful_symbols == ("LT.NS",)
    assert study.failed_symbols == ()
    assert study.fresh_sequence_count == 2
    assert study.external_baseline_used is True
    assert study.is_actionable is False


def test_dataset_tamper_is_detected_by_embedded_fingerprint(tmp_path) -> None:
    frozen = freeze_daily_behavior_sequence_dataset(
        dataset_id="k4-lt-daily-case-01",
        source=_source(),
        inputs=(_input(),),
    )
    path = write_daily_behavior_sequence_dataset(
        frozen,
        tmp_path / "dataset.json",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["symbols"][0]["bars"][3]["close"] = 999.0
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="dataset fingerprint mismatch"):
        load_daily_behavior_sequence_dataset(path)


def test_dataset_rejects_weekly_evidence_timeframe(tmp_path) -> None:
    frozen = freeze_daily_behavior_sequence_dataset(
        dataset_id="k4-lt-daily-case-01",
        source=_source(),
        inputs=(_input(),),
    )
    path = write_daily_behavior_sequence_dataset(
        frozen,
        tmp_path / "dataset.json",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["evidence_timeframe"] = "1W"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="evidence_timeframe must be 1D"):
        load_daily_behavior_sequence_dataset(path)


def test_dataset_rejects_unsupported_schema(tmp_path) -> None:
    frozen = freeze_daily_behavior_sequence_dataset(
        dataset_id="k4-lt-daily-case-01",
        source=_source(),
        inputs=(_input(),),
    )
    path = write_daily_behavior_sequence_dataset(
        frozen,
        tmp_path / "dataset.json",
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["schema_version"] = 999
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported daily sequence dataset"):
        load_daily_behavior_sequence_dataset(path)


def test_freeze_rejects_duplicate_symbol_inputs() -> None:
    first = _input()
    duplicate = DailyBehaviorSequenceStudyInput(
        symbol="lt.ns",
        bars=first.bars.copy(),
        weekly_directions=first.weekly_directions,
        evidence=first.evidence,
    )

    with pytest.raises(ValueError, match="unique symbols"):
        freeze_daily_behavior_sequence_dataset(
            dataset_id="duplicate-case",
            source=_source(),
            inputs=(first, duplicate),
        )


def test_dataset_requires_explicit_source_provenance() -> None:
    with pytest.raises(ValueError, match="source.reference"):
        freeze_daily_behavior_sequence_dataset(
            dataset_id="missing-source",
            source=DailyBehaviorSequenceDatasetSource(
                kind="manual_daily_evidence_review",
                reference=" ",
                prepared_at_utc="2026-09-18T12:30:00Z",
            ),
            inputs=(_input(),),
        )
