"""Causal weekly-direction assignments for M11 daily sequence research.

This module is analysis-only. It maps already-materialized WeeklySetup objects
onto completed daily bars through WeeklyDailyCoordinator. It does not derive
weekly direction from daily prices and does not create weekly qualification.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from audit.daily_behavior_sequence_runner import (
    DailyBehaviorSequenceDirectionAssignment,
)
from daily_completion import completed_daily_only
from trading_calendar import NSETradingCalendar, TradingCalendar
from weekly_daily_coordinator import (
    WeeklyDailyCoordinator,
    weekly_setup_available_session,
    weekly_setup_completion_session,
)
from weekly_setup import WeeklySetup, WeeklySetupDirection


WEEKLY_DIRECTION_ASSIGNMENT_PRODUCER_ID = (
    "weekly-daily-coordinator-causal-assignments-v1"
)


@dataclass(frozen=True, slots=True)
class WeeklyDirectionSourceFingerprint:
    symbol: str
    completed_daily_bar_count: int
    setup_count: int
    first_session: str | None
    last_session: str | None
    sha256: str


@dataclass(frozen=True, slots=True)
class CausalWeeklyDirectionObservation:
    """One armed weekly thesis causally visible to one completed daily bar."""

    bar_index: int
    session: str
    setup_id: str
    signal_week: str
    direction: WeeklySetupDirection


@dataclass(frozen=True, slots=True)
class CausalWeeklyDirectionArchive:
    """Read-only weekly-direction assignments aligned to completed daily bars."""

    symbol: str
    producer_id: str
    completed_daily: pd.DataFrame
    source_fingerprint: WeeklyDirectionSourceFingerprint
    observations: tuple[CausalWeeklyDirectionObservation, ...]

    @property
    def assignments(
        self,
    ) -> tuple[DailyBehaviorSequenceDirectionAssignment, ...]:
        return tuple(
            DailyBehaviorSequenceDirectionAssignment(
                bar_index=item.bar_index,
                direction=item.direction,
            )
            for item in self.observations
        )

    @property
    def assignment_count(self) -> int:
        return len(self.observations)

    @property
    def is_actionable(self) -> bool:
        return False


def _normalize_symbol(symbol: str) -> str:
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise ValueError("symbol cannot be blank")
    return normalized


def _validate_daily_index(daily: pd.DataFrame) -> None:
    if daily.empty:
        raise ValueError("daily data cannot be empty")
    if not isinstance(daily.index, pd.DatetimeIndex):
        raise TypeError("daily data must use a DatetimeIndex")
    if not daily.index.is_monotonic_increasing:
        raise ValueError("daily sessions must be sorted")
    if daily.index.has_duplicates:
        raise ValueError("daily sessions must be unique")


def _relevant_setups(
    symbol: str,
    setups: Iterable[WeeklySetup],
) -> tuple[WeeklySetup, ...]:
    relevant = tuple(
        setup
        for setup in setups
        if setup.symbol.strip().upper() == symbol
    )
    setup_ids = tuple(setup.setup_id for setup in relevant)
    if len(set(setup_ids)) != len(setup_ids):
        raise ValueError("weekly setups require unique setup_id values")
    return relevant


def fingerprint_weekly_direction_source(
    *,
    symbol: str,
    completed_daily: pd.DataFrame,
    setups: Iterable[WeeklySetup],
    calendar: TradingCalendar,
) -> WeeklyDirectionSourceFingerprint:
    """Fingerprint exact session/setup inputs that determine K6 assignments."""

    clean_symbol = _normalize_symbol(symbol)
    _validate_daily_index(completed_daily)
    relevant = _relevant_setups(clean_symbol, setups)

    setup_payload = []
    for setup in sorted(relevant, key=lambda item: item.setup_id):
        completion = weekly_setup_completion_session(
            setup,
            calendar=calendar,
        )
        available = weekly_setup_available_session(
            setup,
            calendar=calendar,
        )
        setup_payload.append(
            {
                "setup_id": setup.setup_id,
                "signal_week": setup.signal_week,
                "direction": setup.direction.value,
                "status": setup.status.value,
                "completion_session": completion.isoformat(),
                "available_session": available.isoformat(),
            }
        )

    sessions = [
        pd.Timestamp(index).date().isoformat()
        for index in completed_daily.index
    ]
    payload = {
        "symbol": clean_symbol,
        "sessions": sessions,
        "setups": setup_payload,
    }
    digest = hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    return WeeklyDirectionSourceFingerprint(
        symbol=clean_symbol,
        completed_daily_bar_count=len(completed_daily),
        setup_count=len(relevant),
        first_session=sessions[0] if sessions else None,
        last_session=sessions[-1] if sessions else None,
        sha256=f"sha256:{digest}",
    )


def produce_causal_weekly_direction_assignments(
    *,
    symbol: str,
    daily: pd.DataFrame,
    setups: Iterable[WeeklySetup],
    now: datetime | pd.Timestamp | str | None = None,
    calendar: TradingCalendar | None = None,
) -> CausalWeeklyDirectionArchive:
    """Map causally visible armed weekly setups onto completed daily bars.

    WeeklyDailyCoordinator remains authoritative for visibility. A setup cannot
    affect the session that completes its weekly bar; it first becomes visible
    on the next exchange session.

    K6 emits a direction only while the coordinator reports the selected setup
    as ARMED, matching the existing DailyEntryEngine behavior boundary. Terminal
    setup snapshots are therefore preserved as non-observing context rather than
    being reinterpreted as active historical direction.
    """

    clean_symbol = _normalize_symbol(symbol)
    _validate_daily_index(daily)

    exchange_calendar = calendar or NSETradingCalendar()
    completed = completed_daily_only(
        daily,
        now=now,
        calendar=exchange_calendar,
    )
    if completed.empty:
        raise ValueError("no completed daily bars are available")
    _validate_daily_index(completed)

    relevant = _relevant_setups(clean_symbol, tuple(setups))
    coordinator = WeeklyDailyCoordinator(exchange_calendar)
    observations: list[CausalWeeklyDirectionObservation] = []

    for bar_index, index in enumerate(completed.index):
        session = pd.Timestamp(index).date()
        context = coordinator.context_for(
            symbol=clean_symbol,
            daily_session=session,
            setups=relevant,
        )
        if context.setup is None or not context.is_armed:
            continue

        observations.append(
            CausalWeeklyDirectionObservation(
                bar_index=bar_index,
                session=session.isoformat(),
                setup_id=context.setup.setup_id,
                signal_week=context.setup.signal_week,
                direction=context.setup.direction,
            )
        )

    return CausalWeeklyDirectionArchive(
        symbol=clean_symbol,
        producer_id=WEEKLY_DIRECTION_ASSIGNMENT_PRODUCER_ID,
        completed_daily=completed.copy(),
        source_fingerprint=fingerprint_weekly_direction_source(
            symbol=clean_symbol,
            completed_daily=completed,
            setups=relevant,
            calendar=exchange_calendar,
        ),
        observations=tuple(observations),
    )


__all__ = [
    "CausalWeeklyDirectionArchive",
    "CausalWeeklyDirectionObservation",
    "WEEKLY_DIRECTION_ASSIGNMENT_PRODUCER_ID",
    "WeeklyDirectionSourceFingerprint",
    "fingerprint_weekly_direction_source",
    "produce_causal_weekly_direction_assignments",
]
