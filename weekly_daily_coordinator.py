from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd

from trading_calendar import TradingCalendar
from weekly_setup import WeeklySetup, WeeklySetupStatus


DateLike = date | datetime | pd.Timestamp | str


def _as_date(value: DateLike) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return pd.Timestamp(value).date()


def weekly_setup_completion_session(
    setup: WeeklySetup,
    *,
    calendar: TradingCalendar,
) -> date:
    """Return the final exchange session that can contribute to setup.signal_week.

    Weekly aggregation uses a Friday-ending period. If Friday is not an exchange
    session, the final session is the most recent session before Saturday.
    """

    week_end = pd.Timestamp(setup.signal_week).to_period("W-FRI").end_time.date()
    if calendar.is_session(week_end):
        return week_end
    return calendar.previous_session(week_end + timedelta(days=1))


def weekly_setup_available_session(
    setup: WeeklySetup,
    *,
    calendar: TradingCalendar,
) -> date:
    """Return the first daily session allowed to consume a weekly setup.

    A setup is created from a completed weekly bar, so the same session that
    completes the weekly bar cannot also consume that setup. Lower-timeframe
    logic first sees it on the next valid exchange session.
    """

    completion = weekly_setup_completion_session(setup, calendar=calendar)
    return calendar.next_session(completion)


@dataclass(frozen=True, slots=True)
class WeeklyDailyContext:
    """Point-in-time weekly context visible to one completed daily session."""

    symbol: str
    daily_session: date
    setup: WeeklySetup | None = None
    weekly_completion_session: date | None = None
    setup_available_session: date | None = None

    @property
    def has_setup(self) -> bool:
        return self.setup is not None

    @property
    def is_armed(self) -> bool:
        return self.setup is not None and self.setup.status is WeeklySetupStatus.ARMED


class WeeklyDailyCoordinator:
    """Select weekly context without leaking future weekly information.

    The coordinator is intentionally read-only. It does not create weekly setups,
    advance lifecycle state, or run daily-entry logic. It only answers which
    weekly setup was causally available to a given daily session.
    """

    def __init__(self, calendar: TradingCalendar) -> None:
        self._calendar = calendar

    def context_for(
        self,
        *,
        symbol: str,
        daily_session: DateLike,
        setups: Iterable[WeeklySetup],
    ) -> WeeklyDailyContext:
        clean_symbol = symbol.strip().upper()
        if not clean_symbol:
            raise ValueError("symbol must not be empty")

        session = _as_date(daily_session)
        if not self._calendar.is_session(session):
            raise ValueError(f"{session.isoformat()} is not a trading session")

        seen_ids: set[str] = set()
        visible: list[tuple[date, date, WeeklySetup]] = []

        for setup in setups:
            if setup.setup_id in seen_ids:
                raise ValueError(f"duplicate weekly setup id: {setup.setup_id}")
            seen_ids.add(setup.setup_id)

            if setup.symbol.strip().upper() != clean_symbol:
                continue

            completion = weekly_setup_completion_session(
                setup,
                calendar=self._calendar,
            )
            available = self._calendar.next_session(completion)
            if available <= session:
                visible.append((completion, available, setup))

        if not visible:
            return WeeklyDailyContext(
                symbol=clean_symbol,
                daily_session=session,
            )

        latest_completion = max(item[0] for item in visible)
        latest = [item for item in visible if item[0] == latest_completion]
        if len(latest) != 1:
            setup_ids = ", ".join(sorted(item[2].setup_id for item in latest))
            raise ValueError(
                "multiple weekly setups share the latest completion session: "
                + setup_ids
            )

        completion, available, setup = latest[0]
        return WeeklyDailyContext(
            symbol=clean_symbol,
            daily_session=session,
            setup=setup,
            weekly_completion_session=completion,
            setup_available_session=available,
        )


__all__ = [
    "WeeklyDailyContext",
    "WeeklyDailyCoordinator",
    "weekly_setup_available_session",
    "weekly_setup_completion_session",
]
