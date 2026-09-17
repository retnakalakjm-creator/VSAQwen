from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Protocol, runtime_checkable
from zoneinfo import ZoneInfo

import pandas as pd


NSE_TIMEZONE = "Asia/Kolkata"
NSE_REGULAR_CLOSE = time(15, 30)


@runtime_checkable
class TradingCalendar(Protocol):
    """Point-in-time exchange-session contract used by scanner timing logic."""

    timezone: str

    def is_session(self, value: date | datetime | pd.Timestamp | str) -> bool:
        """Return whether ``value`` is an exchange trading session."""
        ...

    def session_close(
        self,
        value: date | datetime | pd.Timestamp | str,
    ) -> pd.Timestamp:
        """Return the timezone-aware close timestamp for one trading session."""
        ...

    def is_session_complete(
        self,
        value: date | datetime | pd.Timestamp | str,
        *,
        now: datetime | pd.Timestamp | str | None = None,
    ) -> bool:
        """Return whether the session is known to have closed as of ``now``."""
        ...

    def next_session(
        self,
        value: date | datetime | pd.Timestamp | str,
    ) -> date:
        """Return the first trading session strictly after ``value``."""
        ...

    def previous_session(
        self,
        value: date | datetime | pd.Timestamp | str,
    ) -> date:
        """Return the first trading session strictly before ``value``."""
        ...


def _as_date(value: date | datetime | pd.Timestamp | str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return pd.Timestamp(value).date()


def _local_timestamp(
    value: datetime | pd.Timestamp | str | None,
    *,
    timezone: str,
) -> pd.Timestamp:
    if value is None:
        return pd.Timestamp.now(tz=timezone)

    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize(timezone)
    return timestamp.tz_convert(timezone)


@dataclass(frozen=True, slots=True)
class NSETradingCalendar:
    """Configurable NSE cash-market session calendar.

    The calendar deliberately separates session *rules* from holiday data. Normal
    Monday-Friday dates are sessions, ``closed_dates`` removes exchange holidays
    or exceptional closures, and ``extra_sessions`` adds explicitly announced
    weekend/special sessions (for example a special trading session).

    PR-C1 introduces the causal calendar boundary only. Callers must provide the
    authoritative closure/special-session set for the period they operate on;
    later wiring can source that data without changing scanner timing semantics.
    """

    closed_dates: frozenset[date] = field(default_factory=frozenset)
    extra_sessions: frozenset[date] = field(default_factory=frozenset)
    timezone: str = NSE_TIMEZONE
    regular_close: time = NSE_REGULAR_CLOSE

    def __post_init__(self) -> None:
        overlap = self.closed_dates & self.extra_sessions
        if overlap:
            values = ", ".join(sorted(item.isoformat() for item in overlap))
            raise ValueError(
                "closed_dates and extra_sessions must not overlap: " + values
            )
        # Validate the timezone eagerly so bad configuration cannot silently
        # affect point-in-time scanner decisions later.
        ZoneInfo(self.timezone)

    def is_session(self, value: date | datetime | pd.Timestamp | str) -> bool:
        session_date = _as_date(value)
        if session_date in self.closed_dates:
            return False
        if session_date in self.extra_sessions:
            return True
        return session_date.weekday() < 5

    def session_close(
        self,
        value: date | datetime | pd.Timestamp | str,
    ) -> pd.Timestamp:
        session_date = _as_date(value)
        if not self.is_session(session_date):
            raise ValueError(f"{session_date.isoformat()} is not an NSE trading session")
        close = datetime.combine(session_date, self.regular_close)
        return pd.Timestamp(close, tz=self.timezone)

    def is_session_complete(
        self,
        value: date | datetime | pd.Timestamp | str,
        *,
        now: datetime | pd.Timestamp | str | None = None,
    ) -> bool:
        session_date = _as_date(value)
        if not self.is_session(session_date):
            return False
        current = _local_timestamp(now, timezone=self.timezone)
        # Match the existing weekly guardrail: exactly at the configured close
        # is still considered forming; only a timestamp after close is complete.
        return current > self.session_close(session_date)

    def next_session(
        self,
        value: date | datetime | pd.Timestamp | str,
    ) -> date:
        return self._seek(_as_date(value), step=1)

    def previous_session(
        self,
        value: date | datetime | pd.Timestamp | str,
    ) -> date:
        return self._seek(_as_date(value), step=-1)

    def _seek(self, origin: date, *, step: int) -> date:
        if step not in (-1, 1):
            raise ValueError("step must be -1 or 1")

        candidate = origin
        # A one-year cap prevents an accidental infinite loop from pathological
        # injected configuration while remaining far beyond any real NSE closure.
        for _ in range(366):
            candidate += timedelta(days=step)
            if self.is_session(candidate):
                return candidate
        raise RuntimeError("no NSE trading session found within 366 calendar days")


__all__ = [
    "NSE_REGULAR_CLOSE",
    "NSE_TIMEZONE",
    "NSETradingCalendar",
    "TradingCalendar",
]
