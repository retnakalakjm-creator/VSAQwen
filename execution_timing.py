from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from trading_calendar import TradingCalendar


@dataclass(frozen=True, slots=True)
class NextSessionExecution:
    """Execution availability derived from a signal session and market calendar."""

    signal_session: date
    execution_session: date
    execution_bar_index: int | None
    execution_available: bool


def _as_date(value: date | datetime | pd.Timestamp | str) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return pd.Timestamp(value).date()


def next_session_execution(
    sessions: pd.Index | pd.Series | list[object] | tuple[object, ...],
    *,
    signal_session: date | datetime | pd.Timestamp | str,
    calendar: TradingCalendar,
) -> NextSessionExecution:
    """Resolve execution to the first valid exchange session after the signal.

    The expected execution session always comes from ``calendar.next_session``.
    A matching bar index is exposed only when that exact session is present in
    ``sessions``. Missing sessions are never skipped forward to a later bar,
    preventing accidental execution after a data gap or exchange closure mismatch.
    """

    signal_date = _as_date(signal_session)
    execution_date = calendar.next_session(signal_date)

    execution_bar_index: int | None = None
    for index, value in enumerate(sessions):
        if _as_date(value) == execution_date:
            execution_bar_index = index
            break

    return NextSessionExecution(
        signal_session=signal_date,
        execution_session=execution_date,
        execution_bar_index=execution_bar_index,
        execution_available=execution_bar_index is not None,
    )


__all__ = ["NextSessionExecution", "next_session_execution"]
