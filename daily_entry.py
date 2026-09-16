from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum, auto

from daily_behavior import DailyBehaviorSnapshot, evaluate_daily_behavior
from models import Evidence, EvidenceDirection
from weekly_daily_coordinator import WeeklyDailyContext
from weekly_setup import WeeklySetupDirection


class DailyEntryShadowStatus(StrEnum):
    """Read-only outcome of the shadow daily-entry layer."""

    NO_WEEKLY_SETUP = auto()
    WEEKLY_SETUP_NOT_ARMED = auto()
    OBSERVING = auto()


@dataclass(frozen=True, slots=True)
class DailyEntryShadowResult:
    """Point-in-time daily-entry observation with no execution authority."""

    symbol: str
    daily_session: date
    status: DailyEntryShadowStatus
    weekly_setup_id: str | None = None
    weekly_direction: WeeklySetupDirection | None = None
    weekly_signal_week: str | None = None
    daily_bar_index: int | None = None
    observed_evidence: tuple[Evidence, ...] = ()
    aligned_evidence: tuple[Evidence, ...] = ()
    opposing_evidence: tuple[Evidence, ...] = ()
    neutral_evidence: tuple[Evidence, ...] = ()

    @property
    def has_armed_weekly_setup(self) -> bool:
        return self.status is DailyEntryShadowStatus.OBSERVING

    @property
    def is_actionable(self) -> bool:
        """Shadow output can never become production-actionable."""

        return False


class DailyEntryEngine:
    """Shadow-only daily entry evaluator.

    Weekly context owns direction. Daily evidence is observed relative to that
    weekly thesis. Contrary daily evidence does not reverse or invalidate the
    weekly setup here.
    """

    def evaluate_shadow(
        self,
        *,
        context: WeeklyDailyContext,
        daily_bar_index: int,
        evidence: Iterable[Evidence] = (),
    ) -> DailyEntryShadowResult:
        if daily_bar_index < 0:
            raise ValueError("daily_bar_index cannot be negative")

        current = tuple(
            sorted(
                (item for item in evidence if item.bar_index == daily_bar_index),
                key=lambda item: (item.bar_index, str(item.code)),
            )
        )

        setup = context.setup
        if setup is None:
            return DailyEntryShadowResult(
                symbol=context.symbol,
                daily_session=context.daily_session,
                status=DailyEntryShadowStatus.NO_WEEKLY_SETUP,
                daily_bar_index=daily_bar_index,
                observed_evidence=current,
            )

        if not context.is_armed:
            return DailyEntryShadowResult(
                symbol=context.symbol,
                daily_session=context.daily_session,
                status=DailyEntryShadowStatus.WEEKLY_SETUP_NOT_ARMED,
                weekly_setup_id=setup.setup_id,
                weekly_direction=setup.direction,
                weekly_signal_week=setup.signal_week,
                daily_bar_index=daily_bar_index,
                observed_evidence=current,
            )

        aligned_direction = (
            EvidenceDirection.BULLISH
            if setup.direction is WeeklySetupDirection.BULLISH
            else EvidenceDirection.BEARISH
        )
        opposing_direction = (
            EvidenceDirection.BEARISH
            if aligned_direction is EvidenceDirection.BULLISH
            else EvidenceDirection.BULLISH
        )

        aligned = tuple(item for item in current if item.direction == aligned_direction)
        opposing = tuple(item for item in current if item.direction == opposing_direction)
        neutral = tuple(item for item in current if item.direction == EvidenceDirection.NEUTRAL)

        return DailyEntryShadowResult(
            symbol=context.symbol,
            daily_session=context.daily_session,
            status=DailyEntryShadowStatus.OBSERVING,
            weekly_setup_id=setup.setup_id,
            weekly_direction=setup.direction,
            weekly_signal_week=setup.signal_week,
            daily_bar_index=daily_bar_index,
            observed_evidence=current,
            aligned_evidence=aligned,
            opposing_evidence=opposing,
            neutral_evidence=neutral,
        )

    def evaluate_behavior_shadow(
        self,
        *,
        context: WeeklyDailyContext,
        daily_bar_index: int,
        evidence: Iterable[Evidence] = (),
        lookback_bars: int = 5,
    ) -> DailyBehaviorSnapshot | None:
        """Return behavior-based VSA evidence for an armed weekly setup.

        Named patterns such as NO SUPPLY or TEST are supporting evidence only;
        they are not mandatory gates. If no weekly setup is armed, no positive
        daily behavior snapshot is produced.
        """

        if daily_bar_index < 0:
            raise ValueError("daily_bar_index cannot be negative")
        if lookback_bars <= 0:
            raise ValueError("lookback_bars must be positive")
        if context.setup is None or not context.is_armed:
            return None

        return evaluate_daily_behavior(
            weekly_direction=context.setup.direction,
            daily_bar_index=daily_bar_index,
            evidence=evidence,
            lookback_bars=lookback_bars,
        )


__all__ = [
    "DailyEntryEngine",
    "DailyEntryShadowResult",
    "DailyEntryShadowStatus",
]
