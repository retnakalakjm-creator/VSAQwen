"""Boolean coercion helpers for analysis-only audit datasets.

CSV round-trips can turn booleans into strings. Python's raw ``bool("False")``
is true, so audit filters and metadata counts should use explicit coercion
instead of truthiness.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


TRUE_STRINGS = frozenset({"true", "1", "yes", "y", "on"})
FALSE_STRINGS = frozenset({"false", "0", "no", "n", "off", ""})


def coerce_bool_value(value: Any, *, default: bool = False) -> bool:
    """Return a stable bool for native, numeric, and string-like values."""
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in TRUE_STRINGS:
            return True
        if normalized in FALSE_STRINGS:
            return False
        return default
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)

    return bool(value)


def coerce_bool_series(series: pd.Series, *, default: bool = False) -> pd.Series:
    """Return a boolean Series using :func:`coerce_bool_value` elementwise."""
    return series.map(lambda value: coerce_bool_value(value, default=default)).astype(bool)


__all__ = ["coerce_bool_series", "coerce_bool_value"]
