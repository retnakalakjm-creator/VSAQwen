from __future__ import annotations

from dataclasses import dataclass
import statistics

import pandas as pd

from engine.columns import COL_AVG_SPREAD, COL_SPREAD, COL_VOLUME
from models import Swing, SwingHistorySnapshot, SwingType


@dataclass(slots=True, frozen=True)
class SwingHistoryAnalyzer:
    """
    Immutable historical view of confirmed swings.

    Provides navigation and historical measurements for
    Professional Swing Scoring.
    """

    swings: tuple[Swing, ...]

    current_index: int


    def current(self) -> Swing:
        """
        Return the current swing.
        """

        return self.swings[self.current_index]    
    
    def previous(self) -> Swing | None:
        """
        Return the previous swing if one exists.
        """

        if self.current_index == 0:
            return None

        return self.swings[self.current_index - 1]
    
    def next(self) -> Swing | None:
        """
        Return the next swing if one exists.
        """

        if self.current_index >= len(self.swings) - 1:
            return None

        return self.swings[self.current_index + 1]
    
    def _current_amplitude(self) -> float | None:
        """
        Price movement between the current swing
        and the previous confirmed swing.
        """

        previous = self.previous()

        if previous is None:
            return None

        current = self.current()

        return abs(current.price - previous.price)
    
    def _current_duration(self) -> int | None:
        """
        Number of bars between the current swing
        and the previous confirmed swing.
        """

        previous = self.previous()

        if previous is None:
            return None

        current = self.current()

        return abs(current.bar_index - previous.bar_index)
    
    def last(
        self,
        n: int,
    ) -> tuple[Swing, ...]:
        """
        Return up to the last n swings ending
        with the current swing.
        """

        start = max(0, self.current_index - n + 1)

        return self.swings[start : self.current_index + 1]
    

    def amplitudes(
        self,
        lookback: int | None = None,
    ) -> list[float]:
        """
        Historical swing amplitudes.
        """

        if lookback is not None and lookback <= 0:
            raise ValueError("lookback must be greater than zero")

        if lookback is None:
            swings = self.swings
        else:
            swings = self.last(lookback)

        amplitudes: list[float] = []

        for previous, current in zip(swings[:-1], swings[1:]):
            amplitudes.append(
                abs(current.price - previous.price)
            )

        return amplitudes
    
    def _previous_amplitudes(
        self,
        lookback: int | None = None,
    ) -> list[float]:
        """
        Historical swing amplitudes excluding the
        current swing.
        """

        if lookback is not None and lookback <= 0:
            raise ValueError("lookback must be greater than zero")

        start = max(
            0,
            self.current_index - lookback + 1,
        ) if lookback is not None else 0

        swings = self.swings[start:self.current_index]

        return [
            abs(current.price - previous.price)
            for previous, current in zip(
                swings[:-1],
                swings[1:],
            )
        ]


    def spread_adjusted_amplitudes(
        self,
        metrics: pd.DataFrame,
        lookback: int | None = None,
    ) -> list[float]:
        """
        Historical swing amplitudes normalized by the
        rolling average spread at each confirmed swing.
        """

        if lookback is not None and lookback <= 0:
            raise ValueError(
                "lookback must be greater than zero"
            )

        swings = (
            self.swings
            if lookback is None
            else self.last(lookback)
        )

        adjusted: list[float] = []

        avg_spreads = metrics[COL_AVG_SPREAD].to_numpy(copy=False)

        for previous, current in zip(
            swings[:-1],
            swings[1:],
        ):

            amplitude = abs(
                current.price - previous.price
            )
            
            avg_spread = avg_spreads[current.metrics_index]

            if pd.isna(avg_spread):
                continue

            if avg_spread <= 0:
                continue

            adjusted.append(
                amplitude / avg_spread
            )

        return adjusted

    def spread_adjusted_amplitudes_by_type(
        self,
        metrics: pd.DataFrame,
        swing_type: SwingType,
        lookback: int | None = None,
    ) -> list[float]:
        """
        Historical spread-adjusted amplitudes for one swing type.
        """

        if lookback is not None and lookback <= 0:
            raise ValueError(
                "lookback must be greater than zero"
            )

        swings = (
            self.swings
            if lookback is None
            else self.last(lookback)
        )

        adjusted: list[float] = []
        avg_spreads = metrics[COL_AVG_SPREAD].to_numpy(copy=False)

        for previous, current in zip(
            swings[:-1],
            swings[1:],
        ):

            if current.type != swing_type:
                continue

            amplitude = abs(
                current.price - previous.price
            )

            avg_spread = avg_spreads[current.metrics_index]

            if pd.isna(avg_spread):
                continue

            if avg_spread <= 0:
                continue

            adjusted.append(
                amplitude / avg_spread
            )

        return adjusted
    
    
    def _previous_spread_adjusted_amplitudes_by_type(
        self,
        metrics: pd.DataFrame,
        swing_type: SwingType,
        lookback: int | None = None,
    ) -> list[float]:
        """
        Historical spread-adjusted amplitudes for one swing type,
        excluding the current swing.
        """

        if lookback is not None and lookback <= 0:
            raise ValueError(
                "lookback must be greater than zero"
            )

        start = max(
            0,
            self.current_index - lookback + 1,
        ) if lookback is not None else 0

        swings = self.swings[start:self.current_index]
        adjusted: list[float] = []
        avg_spreads = metrics[COL_AVG_SPREAD].to_numpy(copy=False)

        for previous, current in zip(
            swings[:-1],
            swings[1:],
        ):
            if current.type != swing_type:
                continue

            amplitude = abs(
                current.price - previous.price
            ) 

            avg_spread = avg_spreads[current.metrics_index]

            if pd.isna(avg_spread) or avg_spread <= 0:
                continue

            adjusted.append(
                amplitude / avg_spread
            )

        return adjusted


    def _previous_spread_adjusted_amplitudes(
        self,
        metrics: pd.DataFrame,
        lookback: int | None = None,
    ) -> list[float]:
        """
        Historical spread-adjusted amplitudes
        excluding the current swing.
        """

        if lookback is not None and lookback <= 0:
            raise ValueError(
                "lookback must be greater than zero"
            )

        start = max(
            0,
            self.current_index - lookback + 1,
        ) if lookback is not None else 0

        swings = self.swings[start:self.current_index]
        adjusted: list[float] = []
        avg_spreads = metrics[COL_AVG_SPREAD].to_numpy(copy=False)
        for previous, current in zip(
            swings[:-1],
            swings[1:],
        ):
            amplitude = abs(
                current.price - previous.price
            )

            avg_spread = avg_spreads[current.metrics_index]
            if pd.isna(avg_spread) or avg_spread <= 0:
                continue

            adjusted.append(
                amplitude / avg_spread
            )

        return adjusted


    def durations(
        self,
        lookback: int | None = None,
    ) -> list[int]:
        """
        Historical swing durations.
        """

        if lookback is not None and lookback <= 0:
            raise ValueError("lookback must be greater than zero")

        if lookback is None:
            swings = self.swings
        else:
            swings = self.last(lookback)

        durations: list[int] = []

        for previous, current in zip(swings[:-1], swings[1:]):
            durations.append(
                abs(current.bar_index - previous.bar_index)
            )

        return durations
    

    def _previous_durations(
        self,
        lookback: int | None = None,
    ) -> list[int]:
        """
        Historical swing durations excluding
        the current swing.
        """

        if lookback is not None and lookback <= 0:
            raise ValueError("lookback must be greater than zero")

        start = max(
            0,
            self.current_index - lookback + 1,
        ) if lookback is not None else 0

        swings = self.swings[start:self.current_index]

        return [
            abs(current.bar_index - previous.bar_index)
            for previous, current in zip(
                swings[:-1],
                swings[1:],
            )
        ]
    
    @property
    def count(self) -> int:
        return len(self.swings)
    

    @property
    def has_previous(self) -> bool:
        return self.current_index > 0   
    
    @property
    def is_first(self) -> bool:
        return self.current_index == 0


    @property
    def is_last(self) -> bool:
        return self.current_index == self.count - 1
    

    def metric_values(
        self,
        metrics: pd.DataFrame,
        column: str,
        lookback: int | None = None,
    ) -> list[float]:
        """
        Historical metric values for confirmed swings.
        """

        if lookback is not None and lookback <= 0:
            raise ValueError(
                "lookback must be greater than zero"
            )
        values_column = metrics[column].to_numpy(copy=False)

        swings = (
            self.swings
            if lookback is None
            else self.last(lookback)
        )

        values: list[float] = []

        for swing in swings:
            
            value = values_column[swing.metrics_index]
            if pd.isna(value):
                continue

            values.append(
                float(value)
            )

        return values
    

    def _previous_metric_values(
        self,
        metrics: pd.DataFrame,
        column: str,
        lookback: int | None = None,
    ) -> list[float]:
        """
        Historical metric values excluding
        the current swing.
        """

        if lookback is not None and lookback <= 0:
            raise ValueError(
                "lookback must be greater than zero"
            )
        values_column = metrics[column].to_numpy(copy=False)

        start = max(
            0,
            self.current_index - lookback + 1,
        ) if lookback is not None else 0

        swings = self.swings[start:self.current_index]
        values: list[float] = []

        for swing in swings:
                        
            value = values_column[swing.metrics_index]

            if pd.isna(value):
                continue

            values.append(float(value))

        return values
    
    @classmethod
    def from_swings(
        cls,
        *swings: Swing,
    ) -> "SwingHistoryAnalyzer":

        return cls(
            swings=tuple(swings),
            current_index=len(swings) - 1,
        )
    

    def average_spread_adjusted_amplitude(
        self,
        metrics: pd.DataFrame,
        lookback: int = 10,
    ) -> float:
        """
        Average spread-adjusted swing amplitude,
        excluding the current swing.
        """

        amplitudes = self.previous_spread_adjusted_amplitudes(
            metrics,
            lookback,
        )

        if not amplitudes:
            return 0.0

        return statistics.fmean(amplitudes)


    def average_duration(
        self,
        lookback: int = 10,
    ) -> float:
        """
        Average swing duration excluding
        the current swing.
        """

        durations = self.previous_durations(
            lookback,
        )

        if not durations:
            return 0.0

        return statistics.fmean(durations)


    def average_volume(
        self,
        metrics: pd.DataFrame,
        lookback: int = 10,
    ) -> float:
        """
        Average swing volume excluding
        the current swing.
        """

        volumes = self.previous_metric_values(
            metrics,
            COL_VOLUME,
            lookback,
        )

        if not volumes:
            return 0.0

        return statistics.fmean(volumes)

    def previous_high(self) -> Swing | None:
        """
        Return the most recent HIGH swing before
        the current swing.
        """

        for swing in reversed(
            self.swings[: self.current_index]
        ):

            if swing.type == SwingType.HIGH:
                return swing

        return None

    def previous_low(self) -> Swing | None:
        """
        Return the most recent LOW swing before
        the current swing.
        """

        for swing in reversed(
            self.swings[: self.current_index]
        ):

            if swing.type == SwingType.LOW:
                return swing

        return None

    def max_amplitude(
        self,
        lookback: int = 10,
    ) -> float:
        """
        Largest historical swing amplitude excluding
        the current swing.
        """

        amplitudes = self.previous_amplitudes(
            lookback,
        )

        if not amplitudes:
            return 0.0

        return max(amplitudes)

    def max_duration(
        self,
        lookback: int = 10,
    ) -> int:
        """
        Longest historical swing duration excluding
        the current swing.
        """

        durations = self.previous_durations(
            lookback,
        )

        if not durations:
            return 0

        return max(durations)

    def average_spread(
        self,
        metrics: pd.DataFrame,
        lookback: int = 10,
    ) -> float:
        """
        Average spread of previous confirmed swings.
        """

        spreads = self.previous_metric_values(
            metrics,
            COL_SPREAD,
            lookback,
        )

        if not spreads:
            return 0.0

        return sum(spreads) / len(spreads)
    
    
    def snapshot(
        self,
        metrics: pd.DataFrame,
        lookback: int,
    ) -> SwingHistorySnapshot:
        avg_spreads = metrics[COL_AVG_SPREAD].to_numpy(copy=False)
        current = self.current()
        current_amplitude = self._current_amplitude()
        
        # avg_spread = float(
        #     metrics.iloc[current.metrics_index][COL_AVG_SPREAD]
        # )
        avg_spread = float(avg_spreads[current.metrics_index])
        current_spread_adjusted_amplitude = (
            current_amplitude / avg_spread
            if avg_spread > 0
            else None
        )
        
        spread_adjusted_amplitudes = (
            self._previous_spread_adjusted_amplitudes_by_type(
                metrics,
                current.type,
                lookback,
            )
        )
        
        return SwingHistorySnapshot(
            current_amplitude=current_amplitude,
            current_duration=self._current_duration(),
            current_spread_adjusted_amplitude=current_spread_adjusted_amplitude,
            amplitudes=tuple(
                self._previous_amplitudes(lookback)
            ),
            spread_adjusted_amplitudes=tuple(
                spread_adjusted_amplitudes
            ),
            durations=tuple(
                self._previous_durations(lookback)
            ),
            volumes=tuple(
                self._previous_metric_values(
                    metrics,
                    COL_VOLUME,
                    lookback,
                )
            ),
            spreads=tuple(
                self._previous_metric_values(
                    metrics,
                    COL_SPREAD,
                    lookback,
                )
            ),
        )