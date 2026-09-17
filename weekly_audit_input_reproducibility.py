from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import math

import pandas as pd

from engine.columns import COL_CLOSE, COL_HIGH, COL_LOW, COL_OPEN, COL_VOLUME, COL_WEEK


WEEKLY_INPUT_FINGERPRINT_VERSION = "weekly-ohlcv-v1"
_FINGERPRINT_COLUMNS = (
    COL_WEEK,
    COL_OPEN,
    COL_HIGH,
    COL_LOW,
    COL_CLOSE,
    COL_VOLUME,
)


@dataclass(frozen=True, slots=True)
class WeeklyAuditInputFingerprint:
    """Deterministic identity of the completed weekly OHLCV supplied to an audit."""

    symbol: str
    version: str
    row_count: int
    first_week: str | None
    last_week: str | None
    sha256: str
    columns: tuple[str, ...] = _FINGERPRINT_COLUMNS


@dataclass(frozen=True, slots=True)
class WeeklyAuditInputMismatch:
    symbol: str
    fields: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WeeklyAuditInputComparison:
    matches: bool
    missing_from_left: tuple[str, ...]
    missing_from_right: tuple[str, ...]
    mismatches: tuple[WeeklyAuditInputMismatch, ...]


def _normalize_symbol(symbol: str) -> str:
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise ValueError("symbol cannot be blank")
    return normalized


def _week_text(value: object) -> str:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("weekly input contains a missing week")
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp.isoformat()


def _number_text(value: object) -> str:
    number = float(value)
    if math.isnan(number):
        return "nan"
    if math.isinf(number):
        return "+inf" if number > 0 else "-inf"
    return number.hex()


def fingerprint_weekly_audit_input(
    symbol: str,
    weekly: pd.DataFrame,
) -> WeeklyAuditInputFingerprint:
    """Fingerprint row order plus completed weekly OHLCV values.

    The hash deliberately excludes derived metrics. It represents the exact
    completed-week market input entering MetricsEngine. IEEE-754 ``float.hex``
    encoding avoids locale/CSV formatting differences while preserving exact
    numeric values.
    """

    normalized_symbol = _normalize_symbol(symbol)
    missing = tuple(column for column in _FINGERPRINT_COLUMNS if column not in weekly.columns)
    if missing:
        raise ValueError(f"weekly input missing fingerprint columns: {list(missing)}")

    digest = sha256()
    digest.update(f"{WEEKLY_INPUT_FINGERPRINT_VERSION}\n".encode("utf-8"))
    digest.update(("|".join(_FINGERPRINT_COLUMNS) + "\n").encode("utf-8"))

    first_week: str | None = None
    last_week: str | None = None
    for values in weekly.loc[:, list(_FINGERPRINT_COLUMNS)].itertuples(index=False, name=None):
        week = _week_text(values[0])
        if first_week is None:
            first_week = week
        last_week = week
        encoded = [week, *(_number_text(value) for value in values[1:])]
        digest.update(("|".join(encoded) + "\n").encode("utf-8"))

    return WeeklyAuditInputFingerprint(
        symbol=normalized_symbol,
        version=WEEKLY_INPUT_FINGERPRINT_VERSION,
        row_count=len(weekly),
        first_week=first_week,
        last_week=last_week,
        sha256=digest.hexdigest(),
    )


def compare_weekly_audit_inputs(
    left: tuple[WeeklyAuditInputFingerprint, ...],
    right: tuple[WeeklyAuditInputFingerprint, ...],
) -> WeeklyAuditInputComparison:
    left_by_symbol = {item.symbol: item for item in left}
    right_by_symbol = {item.symbol: item for item in right}
    if len(left_by_symbol) != len(left) or len(right_by_symbol) != len(right):
        raise ValueError("fingerprint sets require unique symbols")

    left_symbols = set(left_by_symbol)
    right_symbols = set(right_by_symbol)
    missing_from_left = tuple(sorted(right_symbols - left_symbols))
    missing_from_right = tuple(sorted(left_symbols - right_symbols))

    mismatches: list[WeeklyAuditInputMismatch] = []
    fields = ("version", "row_count", "first_week", "last_week", "sha256", "columns")
    for symbol in sorted(left_symbols & right_symbols):
        lhs = left_by_symbol[symbol]
        rhs = right_by_symbol[symbol]
        changed = tuple(field for field in fields if getattr(lhs, field) != getattr(rhs, field))
        if changed:
            mismatches.append(WeeklyAuditInputMismatch(symbol=symbol, fields=changed))

    return WeeklyAuditInputComparison(
        matches=not missing_from_left and not missing_from_right and not mismatches,
        missing_from_left=missing_from_left,
        missing_from_right=missing_from_right,
        mismatches=tuple(mismatches),
    )


__all__ = [
    "WEEKLY_INPUT_FINGERPRINT_VERSION",
    "WeeklyAuditInputComparison",
    "WeeklyAuditInputFingerprint",
    "WeeklyAuditInputMismatch",
    "compare_weekly_audit_inputs",
    "fingerprint_weekly_audit_input",
]
