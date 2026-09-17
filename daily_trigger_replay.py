from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum, auto

import pandas as pd

from daily_behavior import DailyBehaviorDimension, DailyBehaviorSnapshot
from execution_timing import next_session_execution
from models import Evidence
from trading_calendar import TradingCalendar
from weekly_daily_coordinator import WeeklyDailyContext
from weekly_setup import WeeklySetupDirection


DateLike = date | datetime | pd.Timestamp | str


class DailyTriggerReplayStatus(StrEnum):
    """Read-only replay state for a behavior-based daily signal."""

    NO_ARMED_WEEKLY_SETUP = auto()
    NO_NEW_BEHAVIOR = auto()
    PENDING_NEXT_SESSION = auto()
    NEXT_SESSION_AVAILABLE = auto()


@dataclass(frozen=True, slots=True)
class DailyTriggerReplayOutput:
    """Auditable shadow output linking daily behavior to next-session timing.

    This object does not authorize an entry, assign a score, choose a price, or
    mutate the weekly setup. It exists so replay/audit can see when fresh daily
    behavior first became observable and when the exact next exchange session
    became available.
    """

    symbol: str
    daily_session: date
    daily_bar_index: int
    status: DailyTriggerReplayStatus
    weekly_setup_id: str | None = None
    weekly_direction: WeeklySetupDirection | None = None
    behavior_dimensions: tuple[DailyBehaviorDimension, ...] = ()
    signal_dimensions: tuple[DailyBehaviorDimension, ...] = ()
    context_evidence: tuple[Evidence, ...] = ()
    signal_evidence: tuple[Evidence, ...] = ()
    execution_session: date | None = None
    execution_bar_index: int | None = None
    execution_available: bool = False

    @property
    def signal_observed(self) -> bool:
        return self.status in {
            DailyTriggerReplayStatus.PENDING_NEXT_SESSION,
            DailyTriggerReplayStatus.NEXT_SESSION_AVAILABLE,
        }

    @property
    def is_actionable(self) -> bool:
        """F3 remains shadow-only even when the next session exists."""

        return False


def _as_date(value: DateLike) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return pd.Timestamp(value).date()


def build_daily_trigger_replay_output(
    *,
    context: WeeklyDailyContext,
    behavior: DailyBehaviorSnapshot,
    sessions: Sequence[object] | pd.Index | pd.Series,
    calendar: TradingCalendar,
) -> DailyTriggerReplayOutput:
    """Build a point-in-time shadow signal and exact next-session replay view.

    A behavior snapshot may contain evidence from a bounded recent lookback. To
    avoid re-emitting the same historical condition on every later bar, F3 only
    observes a *new* signal when at least one supported behavior dimension has
    evidence on ``behavior.daily_bar_index`` itself. Older evidence can still
    provide context, but it cannot by itself create a fresh signal.

    Execution timing is delegated to ``next_session_execution``. The signal bar
    can therefore never execute on itself, and a missing expected next-session
    bar remains pending rather than silently skipping to a later date.
    """

    setup = context.setup
    if setup is None or not context.is_armed:
        return DailyTriggerReplayOutput(
            symbol=context.symbol,
            daily_session=context.daily_session,
            daily_bar_index=behavior.daily_bar_index,
            status=DailyTriggerReplayStatus.NO_ARMED_WEEKLY_SETUP,
            weekly_setup_id=setup.setup_id if setup is not None else None,
            weekly_direction=setup.direction if setup is not None else None,
            behavior_dimensions=behavior.dimensions,
            context_evidence=behavior.observed_evidence,
        )

    if behavior.weekly_direction is not setup.direction:
        raise ValueError(
            "behavior weekly direction does not match the visible weekly setup"
        )

    if behavior.daily_bar_index < 0:
        raise ValueError("behavior daily_bar_index cannot be negative")

    session_values = list(sessions)
    if behavior.daily_bar_index >= len(session_values):
        raise IndexError(behavior.daily_bar_index)

    signal_session = _as_date(session_values[behavior.daily_bar_index])
    if signal_session != context.daily_session:
        raise ValueError(
            "behavior daily bar does not match WeeklyDailyContext.daily_session"
        )

    current_observations = tuple(
        item
        for item in behavior.observations
        if any(evidence.bar_index == behavior.daily_bar_index for evidence in item.evidence)
    )
    signal_dimensions = tuple(item.dimension for item in current_observations)

    signal_evidence_items: list[Evidence] = []
    for observation in current_observations:
        for evidence in observation.evidence:
            if evidence.bar_index != behavior.daily_bar_index:
                continue
            if evidence not in signal_evidence_items:
                signal_evidence_items.append(evidence)
    signal_evidence = tuple(
        sorted(
            signal_evidence_items,
            key=lambda item: (item.bar_index, str(item.code), str(item.direction)),
        )
    )

    if not signal_dimensions:
        return DailyTriggerReplayOutput(
            symbol=context.symbol,
            daily_session=context.daily_session,
            daily_bar_index=behavior.daily_bar_index,
            status=DailyTriggerReplayStatus.NO_NEW_BEHAVIOR,
            weekly_setup_id=setup.setup_id,
            weekly_direction=setup.direction,
            behavior_dimensions=behavior.dimensions,
            context_evidence=behavior.observed_evidence,
        )

    timing = next_session_execution(
        session_values,
        signal_session=context.daily_session,
        calendar=calendar,
    )
    status = (
        DailyTriggerReplayStatus.NEXT_SESSION_AVAILABLE
        if timing.execution_available
        else DailyTriggerReplayStatus.PENDING_NEXT_SESSION
    )

    return DailyTriggerReplayOutput(
        symbol=context.symbol,
        daily_session=context.daily_session,
        daily_bar_index=behavior.daily_bar_index,
        status=status,
        weekly_setup_id=setup.setup_id,
        weekly_direction=setup.direction,
        behavior_dimensions=behavior.dimensions,
        signal_dimensions=signal_dimensions,
        context_evidence=behavior.observed_evidence,
        signal_evidence=signal_evidence,
        execution_session=timing.execution_session,
        execution_bar_index=timing.execution_bar_index,
        execution_available=timing.execution_available,
    )


__all__ = [
    "DailyTriggerReplayOutput",
    "DailyTriggerReplayStatus",
    "build_daily_trigger_replay_output",
]
