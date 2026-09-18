from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from daily_behavior import DailyBehaviorSnapshot
from daily_completion import completed_daily_only
from daily_entry import DailyEntryEngine, DailyEntryShadowResult
from daily_trigger_replay import DailyTriggerReplayOutput, build_daily_trigger_replay_output
from models import Evidence
from scanner import ScannerCandidate
from trading_calendar import NSETradingCalendar, TradingCalendar
from weekly_daily_coordinator import WeeklyDailyContext, WeeklyDailyCoordinator
from weekly_setup import WeeklySetup
from weekly_setup_materializer import materialize_production_weekly_setup


@dataclass(frozen=True, slots=True)
class WeeklyDailyShadowPipelineResult:
    """Auditable composition of the production-weekly -> shadow-daily boundary."""

    symbol: str
    completed_daily_bar_count: int
    daily_bar_index: int
    daily_session: date
    weekly_setup: WeeklySetup | None
    context: WeeklyDailyContext
    observation: DailyEntryShadowResult
    behavior: DailyBehaviorSnapshot | None
    trigger: DailyTriggerReplayOutput | None

    @property
    def is_actionable(self) -> bool:
        """The composed pipeline remains shadow-only."""

        return False


def evaluate_weekly_daily_shadow_pipeline(
    *,
    candidate: ScannerCandidate,
    symbol: str,
    daily: pd.DataFrame,
    evidence: Iterable[Evidence] = (),
    daily_bar_index: int | None = None,
    lookback_bars: int = 5,
    now: datetime | pd.Timestamp | str | None = None,
    calendar: TradingCalendar | None = None,
) -> WeeklyDailyShadowPipelineResult:
    """Compose the existing weekly-production and daily-shadow contracts.

    This function does not run the weekly scanner on daily bars and does not add
    any qualification, scoring, ranking, trigger threshold, alert, or execution
    authority. It only wires together already-defined boundaries:

    production ScannerCandidate -> WeeklySetup -> causal weekly/daily context ->
    daily behavior -> next-session shadow replay.

    Evidence bar indices must align to the completed daily dataframe after
    completed_daily_only filtering.
    """

    clean_symbol = symbol.strip().upper()
    if not clean_symbol:
        raise ValueError("symbol must not be empty")
    if lookback_bars <= 0:
        raise ValueError("lookback_bars must be positive")

    exchange_calendar = calendar or NSETradingCalendar()
    completed = completed_daily_only(
        daily,
        now=now,
        calendar=exchange_calendar,
    )
    if completed.empty:
        raise ValueError("no completed daily bars are available")

    target_index = len(completed) - 1 if daily_bar_index is None else int(daily_bar_index)
    if target_index < 0 or target_index >= len(completed):
        raise IndexError("daily_bar_index is outside completed daily bars")

    session = pd.Timestamp(completed.index[target_index]).date()
    setup = materialize_production_weekly_setup(candidate, symbol=clean_symbol)
    setups = () if setup is None else (setup,)

    context = WeeklyDailyCoordinator(exchange_calendar).context_for(
        symbol=clean_symbol,
        daily_session=session,
        setups=setups,
    )

    current_evidence = tuple(evidence)
    entry_engine = DailyEntryEngine()
    observation = entry_engine.evaluate_shadow(
        context=context,
        daily_bar_index=target_index,
        evidence=current_evidence,
    )
    behavior = entry_engine.evaluate_behavior_shadow(
        context=context,
        daily_bar_index=target_index,
        evidence=current_evidence,
        lookback_bars=lookback_bars,
    )

    trigger = None
    if behavior is not None:
        trigger = build_daily_trigger_replay_output(
            context=context,
            behavior=behavior,
            sessions=completed.index,
            calendar=exchange_calendar,
        )

    return WeeklyDailyShadowPipelineResult(
        symbol=clean_symbol,
        completed_daily_bar_count=len(completed),
        daily_bar_index=target_index,
        daily_session=session,
        weekly_setup=setup,
        context=context,
        observation=observation,
        behavior=behavior,
        trigger=trigger,
    )


__all__ = [
    "WeeklyDailyShadowPipelineResult",
    "evaluate_weekly_daily_shadow_pipeline",
]
