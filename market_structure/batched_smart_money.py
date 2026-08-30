from __future__ import annotations

from models import SmartMoneyScore
from .smart_money import SmartMoneyAnalyzer


class BatchedSmartMoneyAnalyzer(SmartMoneyAnalyzer):
    """Smart Money analyzer with scalar-equivalent batch semantics."""

    @staticmethod
    def score_values_batch(
        *,
        open_values,
        low_values,
        close_values,
        spread_values,
        avg_spread_values,
        volume_values,
        avg_volume_values,
        indices,
        include_components: bool = False,
    ) -> tuple[SmartMoneyScore, ...]:
        scores = list(
            SmartMoneyAnalyzer.score_values_batch(
                open_values=open_values,
                low_values=low_values,
                close_values=close_values,
                spread_values=spread_values,
                avg_spread_values=avg_spread_values,
                volume_values=volume_values,
                avg_volume_values=avg_volume_values,
                indices=indices,
                include_components=include_components,
            )
        )

        # score_values() only suppresses Stopping Volume on the first bar.
        # Climactic scoring remains active there, so restore the first result
        # from the scalar implementation when the batch contains index 0.
        for position, index in enumerate(indices):
            if int(index) != 0:
                continue

            scores[position] = SmartMoneyAnalyzer().score_values(
                bar_count=1,
                open_value=float(open_values[index]),
                low_value=float(low_values[index]),
                close_value=float(close_values[index]),
                spread_value=float(spread_values[index]),
                avg_spread=float(avg_spread_values[index]),
                volume_value=float(volume_values[index]),
                avg_volume=float(avg_volume_values[index]),
                include_components=include_components,
            )

        return tuple(scores)
