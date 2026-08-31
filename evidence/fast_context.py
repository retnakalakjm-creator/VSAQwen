from __future__ import annotations

from engine.columns import (
    COL_BODY,
    COL_CLOSE,
    COL_CLOSE_POSITION,
    COL_CLOSE_RATIO,
    COL_DIRECTION,
    COL_HIGH,
    COL_LOW,
    COL_LOWER_SHADOW,
    COL_OPEN,
    COL_PREV_CLOSE,
    COL_PREV_HIGH,
    COL_PREV_LOW,
    COL_PREV_SPREAD,
    COL_SPREAD_CLASS,
    COL_SPREAD_RATIO,
    COL_UPPER_SHADOW,
    COL_VOLUME_CLASS,
    COL_VOLUME_RATIO,
    COL_WEEK,
)
from models import BarContext, BackgroundContext, ClosePosition, Direction, SpreadClass, VolumeClass

_CONTEXT_COLUMNS = (
    COL_WEEK,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
    COL_DIRECTION,
    COL_CLOSE_POSITION,
    COL_SPREAD_RATIO,
    COL_VOLUME_RATIO,
    COL_OPEN,
    COL_HIGH,
    COL_LOW,
    COL_CLOSE,
    COL_BODY,
    COL_UPPER_SHADOW,
    COL_LOWER_SHADOW,
    COL_CLOSE_RATIO,
    COL_PREV_HIGH,
    COL_PREV_LOW,
    COL_PREV_CLOSE,
    COL_PREV_SPREAD,
)


def create_context_fast(self) -> BackgroundContext:
    assert self._metrics is not None
    assert self._trend is not None

    recent = self._recent
    assert not recent.empty

    bars = tuple(
        BarContext(
            week_beginning=str(week),
            bar_index=int(index),
            spread=SpreadClass(int(spread_class)),
            volume=VolumeClass(int(volume_class)),
            direction=Direction(int(direction)),
            close_position=ClosePosition(int(close_position)),
            spread_ratio=float(spread_ratio),
            volume_ratio=float(volume_ratio),
            open=float(open_price),
            high=float(high),
            low=float(low),
            close_price=float(close_price),
            body=float(body),
            upper_shadow=float(upper_shadow),
            lower_shadow=float(lower_shadow),
            close_ratio=float(close_ratio),
            prev_high=float(prev_high),
            prev_low=float(prev_low),
            prev_close=float(prev_close),
            prev_spread=float(prev_spread),
        )
        for index, (
            week,
            spread_class,
            volume_class,
            direction,
            close_position,
            spread_ratio,
            volume_ratio,
            open_price,
            high,
            low,
            close_price,
            body,
            upper_shadow,
            lower_shadow,
            close_ratio,
            prev_high,
            prev_low,
            prev_close,
            prev_spread,
        ) in zip(recent.index, recent.loc[:, _CONTEXT_COLUMNS].itertuples(index=False, name=None))
    )

    current = bars[-1]
    previous = bars[-2] if len(bars) >= 2 else None

    return BackgroundContext(
        background=self._background,
        recent=recent,
        trend=self._trend,
        bars=bars,
        current=current,
        previous=previous,
        structural_swings=self._structural_swings,
        structural_pattern=self._structural_pattern,
        vsa_context=self._vsa_context,
    )


__all__ = ["create_context_fast"]
