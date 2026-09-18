from __future__ import annotations

import pandas as pd
import pytest

from audit.offline_daily_evidence import (
    DAILY_EVIDENCE_PRODUCER_ID,
    evaluate_daily_evidence_prefix,
    fingerprint_daily_evidence_source,
    produce_offline_daily_evidence,
)
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection
from trading_calendar import NSETradingCalendar


def _daily(rows: int = 26) -> pd.DataFrame:
    index = pd.bdate_range("2026-01-05", periods=rows, name="date")
    base = [100.0 + index_ * 0.8 for index_ in range(rows)]
    return pd.DataFrame(
        {
            "open": [value - 0.2 for value in base],
            "high": [value + 1.0 for value in base],
            "low": [value - 1.0 for value in base],
            "close": [value + (0.3 if index_ % 2 == 0 else -0.1) for index_, value in enumerate(base)],
            "volume": [1_000_000.0 + index_ * 20_000.0 for index_ in range(rows)],
        },
        index=index,
    )


def _evidence(bar_index: int) -> Evidence:
    return Evidence(
        code=EvidenceCode.NO_SUPPLY,
        category=EvidenceCategory.SIGNAL,
        direction=EvidenceDirection.BULLISH,
        strength=0.8,
        weight=1.0,
        observation="daily-prefix-test",
        description="daily-prefix-test",
        bar_index=bar_index,
        week_beginning=f"bar-{bar_index}",
    )


def test_offline_daily_evidence_passes_only_causal_prefixes() -> None:
    daily = _daily(24)
    prefix_lengths: list[int] = []

    def evaluator(prefix: pd.DataFrame) -> tuple[Evidence, ...]:
        prefix_lengths.append(len(prefix))
        return (_evidence(len(prefix) - 1),)

    archive = produce_offline_daily_evidence(
        symbol="lt.ns",
        daily=daily,
        now="2026-03-01T16:00:00+05:30",
        calendar=NSETradingCalendar(),
        min_target_index=20,
        prefix_evaluator=evaluator,
    )

    assert archive.symbol == "LT.NS"
    assert archive.producer_id == DAILY_EVIDENCE_PRODUCER_ID
    assert prefix_lengths == [21, 22, 23, 24]
    assert tuple(item.bar_index for item in archive.observations) == (20, 21, 22, 23)
    assert tuple(item.evidence[0].bar_index for item in archive.observations) == (
        20,
        21,
        22,
        23,
    )
    assert archive.evidence_count == 4
    assert archive.is_actionable is False
    assert all(item.is_actionable is False for item in archive.observations)


def test_offline_daily_evidence_excludes_forming_daily_session() -> None:
    daily = _daily(25)
    last_session = daily.index[-1]
    now = pd.Timestamp(last_session).tz_localize("Asia/Kolkata") + pd.Timedelta(
        hours=12
    )

    seen_lengths: list[int] = []

    def evaluator(prefix: pd.DataFrame) -> tuple[Evidence, ...]:
        seen_lengths.append(len(prefix))
        return (_evidence(len(prefix) - 1),)

    archive = produce_offline_daily_evidence(
        symbol="TEST.NS",
        daily=daily,
        now=now,
        calendar=NSETradingCalendar(),
        min_target_index=20,
        prefix_evaluator=evaluator,
    )

    assert len(archive.completed_daily) == 24
    assert archive.completed_daily.index[-1] == daily.index[-2]
    assert seen_lengths[-1] == 24


def test_offline_daily_evidence_rejects_non_target_bar_output() -> None:
    daily = _daily(22)

    def bad_evaluator(prefix: pd.DataFrame) -> tuple[Evidence, ...]:
        return (_evidence(len(prefix) - 2),)

    with pytest.raises(ValueError, match="non-target-bar evidence"):
        produce_offline_daily_evidence(
            symbol="TEST.NS",
            daily=daily,
            now="2026-03-01T16:00:00+05:30",
            min_target_index=20,
            prefix_evaluator=bad_evaluator,
        )


def test_source_fingerprint_is_stable_and_price_sensitive() -> None:
    daily = _daily(24)
    first = fingerprint_daily_evidence_source("lt.ns", daily)
    second = fingerprint_daily_evidence_source("LT.NS", daily.copy())

    changed = daily.copy()
    changed.iloc[10, changed.columns.get_loc("close")] += 3.0
    third = fingerprint_daily_evidence_source("LT.NS", changed)

    assert first == second
    assert first.symbol == "LT.NS"
    assert first.row_count == 24
    assert first.sha256.startswith("sha256:")
    assert third.sha256 != first.sha256


def test_future_extension_does_not_change_existing_prefix_observations() -> None:
    base = _daily(24)
    extended = _daily(28)

    def evaluator(prefix: pd.DataFrame) -> tuple[Evidence, ...]:
        target = len(prefix) - 1
        if target % 2 == 0:
            return (_evidence(target),)
        return ()

    base_archive = produce_offline_daily_evidence(
        symbol="TEST.NS",
        daily=base,
        now="2026-03-01T16:00:00+05:30",
        min_target_index=20,
        prefix_evaluator=evaluator,
    )
    extended_archive = produce_offline_daily_evidence(
        symbol="TEST.NS",
        daily=extended,
        now="2026-03-01T16:00:00+05:30",
        min_target_index=20,
        prefix_evaluator=evaluator,
    )

    assert extended_archive.observations[: len(base_archive.observations)] == (
        base_archive.observations
    )


def test_existing_vsa_stack_daily_prefix_smoke_is_target_bar_only() -> None:
    daily = _daily(23)
    prefix = daily.iloc[:21].copy()

    evidence = evaluate_daily_evidence_prefix(prefix)

    assert isinstance(evidence, tuple)
    assert all(item.bar_index == 20 for item in evidence)


def test_default_producer_uses_existing_stack_without_actionability() -> None:
    daily = _daily(22)

    archive = produce_offline_daily_evidence(
        symbol="TEST.NS",
        daily=daily,
        now="2026-03-01T16:00:00+05:30",
        min_target_index=20,
    )

    assert archive.evaluated_bar_count == 2
    assert all(
        item.bar_index in (20, 21)
        for item in archive.evidence
    )
    assert archive.is_actionable is False
