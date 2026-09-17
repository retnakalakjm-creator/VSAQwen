from __future__ import annotations

from datetime import datetime

import pandas as pd

from trading_calendar import NSETradingCalendar, TradingCalendar


def completed_daily_only(
    daily: pd.DataFrame,
    *,
    now: datetime | pd.Timestamp | str | None = None,
    calendar: TradingCalendar | None = None,
) -> pd.DataFrame:
    """Return only daily bars whose exchange sessions are causally complete.

    A daily OHLCV row is eligible only when its date is a trading session and
    that session has closed strictly before ``now`` according to the supplied
    trading calendar. This prevents the current forming daily candle from
    leaking into daily VSA or entry logic.

    The input shape and index are preserved. Callers that require authoritative
    NSE holidays/special sessions should inject an ``NSETradingCalendar`` with
    those closure/session dates configured.
    """

    if daily.empty:
        return daily.copy()
    if not isinstance(daily.index, pd.DatetimeIndex):
        raise TypeError("daily data must use a DatetimeIndex")

    exchange_calendar = calendar or NSETradingCalendar()
    completed_mask = [
        exchange_calendar.is_session_complete(timestamp, now=now)
        for timestamp in daily.index
    ]
    return daily.loc[completed_mask].copy()


__all__ = ["completed_daily_only"]
