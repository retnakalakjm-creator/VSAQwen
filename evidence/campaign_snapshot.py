from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

import config
from engine.columns import COL_CLOSE, COL_CLOSE_POSITION, COL_DIRECTION
from models import BackgroundContext, TrendDirection, SwingType


@dataclass(frozen=True, slots=True)
class CampaignSnapshot:
    """Minimal point-in-time state required by campaign evaluation."""

    recent_up_bars: int
    recent_down_bars: int
    recent_higher_closes: int
    recent_lower_closes: int
    recent_strong_closes: int
    recent_weak_closes: int
    trend_direction: TrendDirection

    high_scores: tuple[float, ...]
    high_amplitudes: tuple[float, ...]
    low_scores: tuple[float, ...]
    low_amplitudes: tuple[float, ...]

    @classmethod
    def from_context(cls, ctx: BackgroundContext) -> "CampaignSnapshot":
        return cls.from_parts(
            bars=ctx.bars,
            trend_direction=ctx.trend.direction,
            structural_swings=ctx.structural_swings,
        )

    @classmethod
    def from_parts(
        cls,
        *,
        bars: tuple,
        trend_direction: TrendDirection,
        structural_swings: tuple,
    ) -> "CampaignSnapshot":
        recent = bars[-config.BACKGROUND_LOOKBACK :]

        higher_closes = sum(
            current.close_price > previous.close_price
            for previous, current in zip(recent, recent[1:])
        )
        lower_closes = sum(
            current.close_price < previous.close_price
            for previous, current in zip(recent, recent[1:])
        )

        highs = [
            item
            for item in structural_swings
            if item.swing.type is SwingType.HIGH
        ][-2:]
        lows = [
            item
            for item in structural_swings
            if item.swing.type is SwingType.LOW
        ][-2:]

        return cls(
            recent_up_bars=sum(int(bar.direction) > 0 for bar in recent),
            recent_down_bars=sum(int(bar.direction) < 0 for bar in recent),
            recent_higher_closes=higher_closes,
            recent_lower_closes=lower_closes,
            recent_strong_closes=sum(
                int(bar.close_position) >= 3 for bar in recent
            ),
            recent_weak_closes=sum(
                int(bar.close_position) <= 1 for bar in recent
            ),
            trend_direction=trend_direction,
            high_scores=tuple(
                float(item.evaluation.smart_money.overall)
                for item in highs
            ),
            high_amplitudes=tuple(
                float(item.evaluation.structure.snapshot.current_spread_adjusted_amplitude)
                for item in highs
                if item.evaluation.structure.snapshot.current_spread_adjusted_amplitude
                is not None
            ),
            low_scores=tuple(
                float(item.evaluation.smart_money.overall)
                for item in lows
            ),
            low_amplitudes=tuple(
                float(item.evaluation.structure.snapshot.current_spread_adjusted_amplitude)
                for item in lows
                if item.evaluation.structure.snapshot.current_spread_adjusted_amplitude
                is not None
            ),
        )

    @classmethod
    def from_metrics(
        cls,
        metrics: pd.DataFrame,
        *,
        trend_direction: TrendDirection,
        structural_swings: tuple,
    ) -> "CampaignSnapshot":
        """Build candidate-time campaign state directly from metric rows."""
        if metrics.empty:
            raise ValueError("CampaignSnapshot requires non-empty metrics.")

        recent = metrics.tail(config.BACKGROUND_LOOKBACK)
        close = recent[COL_CLOSE]

        highs = [
            item
            for item in structural_swings
            if item.swing.type is SwingType.HIGH
        ][-2:]
        lows = [
            item
            for item in structural_swings
            if item.swing.type is SwingType.LOW
        ][-2:]

        return cls(
            recent_up_bars=int((recent[COL_DIRECTION] > 0).sum()),
            recent_down_bars=int((recent[COL_DIRECTION] < 0).sum()),
            recent_higher_closes=int((close.diff() > 0).sum()),
            recent_lower_closes=int((close.diff() < 0).sum()),
            recent_strong_closes=int((recent[COL_CLOSE_POSITION] >= 3).sum()),
            recent_weak_closes=int((recent[COL_CLOSE_POSITION] <= 1).sum()),
            trend_direction=trend_direction,
            high_scores=tuple(
                float(item.evaluation.smart_money.overall)
                for item in highs
            ),
            high_amplitudes=tuple(
                float(item.evaluation.structure.snapshot.current_spread_adjusted_amplitude)
                for item in highs
                if item.evaluation.structure.snapshot.current_spread_adjusted_amplitude
                is not None
            ),
            low_scores=tuple(
                float(item.evaluation.smart_money.overall)
                for item in lows
            ),
            low_amplitudes=tuple(
                float(item.evaluation.structure.snapshot.current_spread_adjusted_amplitude)
                for item in lows
                if item.evaluation.structure.snapshot.current_spread_adjusted_amplitude
                is not None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["trend_direction"] = self.trend_direction.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CampaignSnapshot":
        return cls(
            recent_up_bars=int(data["recent_up_bars"]),
            recent_down_bars=int(data["recent_down_bars"]),
            recent_higher_closes=int(data["recent_higher_closes"]),
            recent_lower_closes=int(data["recent_lower_closes"]),
            recent_strong_closes=int(data["recent_strong_closes"]),
            recent_weak_closes=int(data["recent_weak_closes"]),
            trend_direction=TrendDirection(data["trend_direction"]),
            high_scores=tuple(float(value) for value in data["high_scores"]),
            high_amplitudes=tuple(float(value) for value in data["high_amplitudes"]),
            low_scores=tuple(float(value) for value in data["low_scores"]),
            low_amplitudes=tuple(float(value) for value in data["low_amplitudes"]),
        )

    def has_recent_strength(self) -> bool:
        if len(self.high_scores) < 2 or len(self.high_amplitudes) < 2:
            return False
        return (
            self.high_scores[-2] >= config.MIN_PROFESSIONAL_SWING_SCORE
            and self.high_scores[-1] >= config.MIN_PROFESSIONAL_SWING_SCORE
            and self.high_amplitudes[-1] >= self.high_amplitudes[-2]
        )

    def has_recent_weakness(self) -> bool:
        if len(self.low_scores) < 2 or len(self.low_amplitudes) < 2:
            return False
        return (
            self.low_amplitudes[-1] < self.low_amplitudes[-2]
            and self.low_scores[-1] < self.low_scores[-2]
        )

    def has_buying_campaign(self) -> bool:
        score = 0
        if self.trend_direction is TrendDirection.UP:
            score += 1
        if self.recent_up_bars >= config.CAMPAIGN_MIN_UP_BARS:
            score += 1
        if self.recent_higher_closes >= config.CAMPAIGN_MIN_HIGHER_CLOSES:
            score += 1
        if self.recent_strong_closes >= config.CAMPAIGN_MIN_STRONG_CLOSES:
            score += 1
        if self.has_recent_strength():
            score += 1
        return score >= config.CAMPAIGN_REQUIRED_SCORE

    def has_selling_campaign(self) -> bool:
        score = 0
        if self.trend_direction is TrendDirection.DOWN:
            score += 1
        if self.recent_down_bars >= config.CAMPAIGN_MIN_DOWN_BARS:
            score += 1
        if self.recent_lower_closes >= config.CAMPAIGN_MIN_LOWER_CLOSES:
            score += 1
        if self.recent_weak_closes >= config.CAMPAIGN_MIN_WEAK_CLOSES:
            score += 1
        if self.has_recent_weakness():
            score += 1
        return score >= config.CAMPAIGN_REQUIRED_SCORE


__all__ = ["CampaignSnapshot"]
