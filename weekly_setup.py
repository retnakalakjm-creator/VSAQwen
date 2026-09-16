from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum, auto
from math import isfinite

from background.qualification import PatternQualification
from models import Evidence


class WeeklySetupDirection(StrEnum):
    """Weekly directional thesis handed to lower-timeframe entry logic."""

    BULLISH = auto()
    BEARISH = auto()


class WeeklySetupStatus(StrEnum):
    """Lifecycle of a qualified weekly setup."""

    ARMED = auto()
    TRIGGERED = auto()
    INVALIDATED = auto()
    EXPIRED = auto()


@dataclass(frozen=True, slots=True)
class WeeklyPriceZone:
    """Closed weekly price zone used by later support/resistance work."""

    lower: float
    upper: float

    def __post_init__(self) -> None:
        if not isfinite(self.lower) or not isfinite(self.upper):
            raise ValueError("weekly price-zone bounds must be finite")
        if self.lower > self.upper:
            raise ValueError("weekly price-zone lower bound must be <= upper bound")


@dataclass(frozen=True, slots=True)
class WeeklySetup:
    """Immutable weekly context handed to the future daily entry engine.

    A ``WeeklySetup`` represents a weekly thesis that is already known from a
    completed weekly bar. It does not contain daily-entry logic and it does not
    prescribe an expiry duration. Expiry policy remains a later empirical
    decision; this model only represents the lifecycle state.
    """

    setup_id: str
    symbol: str
    direction: WeeklySetupDirection
    signal_week: str
    qualification: PatternQualification
    weekly_confidence: float
    weekly_net_strength: float
    weekly_net_pressure: float
    qualifying_evidence: tuple[Evidence, ...] = ()
    supporting_evidence: tuple[Evidence, ...] = ()
    support_zone: WeeklyPriceZone | None = None
    resistance_zone: WeeklyPriceZone | None = None
    invalidation_level: float | None = None
    status: WeeklySetupStatus = WeeklySetupStatus.ARMED

    def __post_init__(self) -> None:
        if not self.setup_id.strip():
            raise ValueError("setup_id must not be empty")
        if not self.symbol.strip():
            raise ValueError("symbol must not be empty")
        if not self.signal_week.strip():
            raise ValueError("signal_week must not be empty")

        numeric_values = {
            "weekly_confidence": self.weekly_confidence,
            "weekly_net_strength": self.weekly_net_strength,
            "weekly_net_pressure": self.weekly_net_pressure,
        }
        if self.invalidation_level is not None:
            numeric_values["invalidation_level"] = self.invalidation_level
        for name, value in numeric_values.items():
            if not isfinite(value):
                raise ValueError(f"{name} must be finite")

        expected = (
            PatternQualification.PERSISTENT_BULLISH
            if self.direction is WeeklySetupDirection.BULLISH
            else PatternQualification.PERSISTENT_BEARISH
        )
        if self.qualification is not expected:
            raise ValueError(
                "weekly setup direction must match its persistent qualification"
            )

    @property
    def is_armed(self) -> bool:
        return self.status is WeeklySetupStatus.ARMED

    @property
    def is_terminal(self) -> bool:
        return self.status in {
            WeeklySetupStatus.TRIGGERED,
            WeeklySetupStatus.INVALIDATED,
            WeeklySetupStatus.EXPIRED,
        }

    def transition_to(self, status: WeeklySetupStatus) -> "WeeklySetup":
        """Return the next immutable lifecycle state.

        Weekly setups may leave ``ARMED`` exactly once. Terminal states cannot
        be rewritten into a different lifecycle outcome; repeating the current
        status is idempotent.
        """

        if status is self.status:
            return self
        if self.status is not WeeklySetupStatus.ARMED:
            raise ValueError(
                f"cannot transition terminal weekly setup from {self.status} to {status}"
            )
        if status is WeeklySetupStatus.ARMED:
            return self
        return replace(self, status=status)


def build_weekly_setup_id(
    symbol: str,
    signal_week: str,
    direction: WeeklySetupDirection,
) -> str:
    """Build a stable identity for one symbol/week/direction setup."""

    clean_symbol = symbol.strip().upper()
    clean_week = signal_week.strip()
    if not clean_symbol:
        raise ValueError("symbol must not be empty")
    if not clean_week:
        raise ValueError("signal_week must not be empty")
    return f"{clean_symbol}:{clean_week}:{direction.value}"


__all__ = [
    "WeeklyPriceZone",
    "WeeklySetup",
    "WeeklySetupDirection",
    "WeeklySetupStatus",
    "build_weekly_setup_id",
]
