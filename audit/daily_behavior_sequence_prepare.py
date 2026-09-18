"""Compose K5 daily Evidence and K6 weekly direction into a frozen K4 case.

This module is analysis-only. It does not create a new detector, weekly
qualification rule, score, trigger, alert, or order path.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

from audit.daily_behavior_sequence_dataset import (
    DailyBehaviorSequenceDatasetSource,
    FrozenDailyBehaviorSequenceDataset,
    freeze_daily_behavior_sequence_dataset,
    write_daily_behavior_sequence_dataset,
)
from audit.daily_behavior_sequence_runner import DailyBehaviorSequenceStudyInput
from audit.offline_daily_evidence import (
    DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    DailyEvidencePrefixEvaluator,
    DailyEvidenceSourceFingerprint,
    OfflineDailyEvidenceArchive,
    produce_offline_daily_evidence,
)
from audit.weekly_direction_assignments import (
    CausalWeeklyDirectionArchive,
    WeeklyDirectionSourceFingerprint,
    produce_causal_weekly_direction_assignments,
)
from engine.columns import COL_CLOSE, COL_HIGH, COL_LOW
from trading_calendar import NSETradingCalendar, TradingCalendar
from weekly_setup import WeeklySetup


DAILY_SEQUENCE_COMPOSER_ID = "k5-k6-causal-k4-composer-v1"
DAILY_SEQUENCE_COMPOSER_SOURCE_KIND = "k5_k6_causal_daily_sequence"


@dataclass(frozen=True, slots=True)
class PreparedDailyBehaviorSequenceCase:
    """Auditable composition result for one symbol-level frozen K4 case."""

    symbol: str
    composer_id: str
    evidence_archive: OfflineDailyEvidenceArchive
    weekly_direction_archive: CausalWeeklyDirectionArchive
    dataset: FrozenDailyBehaviorSequenceDataset

    @property
    def study_input(self) -> DailyBehaviorSequenceStudyInput:
        return self.dataset.inputs[0]

    @property
    def daily_source_fingerprint(self) -> DailyEvidenceSourceFingerprint:
        return self.evidence_archive.source_fingerprint

    @property
    def weekly_source_fingerprint(self) -> WeeklyDirectionSourceFingerprint:
        return self.weekly_direction_archive.source_fingerprint

    @property
    def is_actionable(self) -> bool:
        return False


def _same_completed_sessions(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    if len(left) != len(right):
        return False
    return pd.DatetimeIndex(left.index).equals(pd.DatetimeIndex(right.index))


def _composition_notes(
    *,
    evidence_archive: OfflineDailyEvidenceArchive,
    weekly_archive: CausalWeeklyDirectionArchive,
    notes: str,
) -> str:
    parts = [
        f"composer={DAILY_SEQUENCE_COMPOSER_ID}",
        f"daily_evidence_producer={evidence_archive.producer_id}",
        f"daily_source={evidence_archive.source_fingerprint.sha256}",
        f"weekly_direction_producer={weekly_archive.producer_id}",
        f"weekly_source={weekly_archive.source_fingerprint.sha256}",
    ]
    clean_notes = str(notes).strip()
    if clean_notes:
        parts.append(clean_notes)
    return "; ".join(parts)


def prepare_daily_behavior_sequence_case(
    *,
    dataset_id: str,
    symbol: str,
    daily: pd.DataFrame,
    weekly_setups: Iterable[WeeklySetup],
    source_reference: str,
    prepared_at_utc: str,
    now: datetime | pd.Timestamp | str | None = None,
    calendar: TradingCalendar | None = None,
    min_target_index: int = DEFAULT_DAILY_EVIDENCE_MIN_TARGET_INDEX,
    prefix_evaluator: DailyEvidencePrefixEvaluator | None = None,
    notes: str = "",
) -> PreparedDailyBehaviorSequenceCase:
    """Build one frozen K4 input from genuine K5/K6 causal producers.

    The same raw daily frame, now boundary, and trading calendar are supplied
    to K5 and K6 independently. Their retained completed-session sequences must
    match exactly before the K4 input can be frozen.

    Weekly direction remains sourced only from WeeklySetup objects through K6;
    K7 never derives direction from daily prices.
    """

    exchange_calendar = calendar or NSETradingCalendar()
    setups = tuple(weekly_setups)

    evidence_archive = produce_offline_daily_evidence(
        symbol=symbol,
        daily=daily,
        now=now,
        calendar=exchange_calendar,
        min_target_index=min_target_index,
        prefix_evaluator=prefix_evaluator,
    )
    weekly_archive = produce_causal_weekly_direction_assignments(
        symbol=symbol,
        daily=daily,
        setups=setups,
        now=now,
        calendar=exchange_calendar,
    )

    if evidence_archive.symbol != weekly_archive.symbol:
        raise ValueError("K5/K6 symbol mismatch")
    if not _same_completed_sessions(
        evidence_archive.completed_daily,
        weekly_archive.completed_daily,
    ):
        raise ValueError("K5/K6 completed daily session mismatch")

    completed = evidence_archive.completed_daily
    bars = completed.loc[:, [COL_CLOSE, COL_HIGH, COL_LOW]].copy()
    study_input = DailyBehaviorSequenceStudyInput(
        symbol=evidence_archive.symbol,
        bars=bars,
        weekly_directions=weekly_archive.assignments,
        evidence=evidence_archive.evidence,
    )

    source = DailyBehaviorSequenceDatasetSource(
        kind=DAILY_SEQUENCE_COMPOSER_SOURCE_KIND,
        reference=str(source_reference).strip(),
        prepared_at_utc=str(prepared_at_utc).strip(),
        notes=_composition_notes(
            evidence_archive=evidence_archive,
            weekly_archive=weekly_archive,
            notes=notes,
        ),
    )
    dataset = freeze_daily_behavior_sequence_dataset(
        dataset_id=dataset_id,
        source=source,
        inputs=(study_input,),
    )

    return PreparedDailyBehaviorSequenceCase(
        symbol=evidence_archive.symbol,
        composer_id=DAILY_SEQUENCE_COMPOSER_ID,
        evidence_archive=evidence_archive,
        weekly_direction_archive=weekly_archive,
        dataset=dataset,
    )


def write_prepared_daily_behavior_sequence_case(
    case: PreparedDailyBehaviorSequenceCase,
    path: str | Path,
) -> Path:
    """Write the composed case through the existing K4 canonical writer."""

    if case.is_actionable:
        raise ValueError("prepared daily sequence research case cannot be actionable")
    return write_daily_behavior_sequence_dataset(case.dataset, path)


__all__ = [
    "DAILY_SEQUENCE_COMPOSER_ID",
    "DAILY_SEQUENCE_COMPOSER_SOURCE_KIND",
    "PreparedDailyBehaviorSequenceCase",
    "prepare_daily_behavior_sequence_case",
    "write_prepared_daily_behavior_sequence_case",
]
