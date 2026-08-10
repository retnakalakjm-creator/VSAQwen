from __future__ import annotations

class StrengthCalculator:

    @staticmethod
    def no_demand(
        current_bar,
        previous_bar,
    ) -> float:

        volume_drop = max(
            0.0,
            previous_bar.volume_ratio -
            current_bar.volume_ratio,
        )

        return min(
            1.0,
            0.70 + volume_drop,
        )


    @staticmethod
    def no_supply(
        current_bar,
        previous_bar,
    ) -> float:

        volume_drop = max(
            0.0,
            previous_bar.volume_ratio -
            current_bar.volume_ratio,
        )

        return min(
            1.0,
            0.70 + volume_drop,
        )

    @staticmethod
    def test(
        current_bar,
        previous_bar,
    ) -> float:

        volume_drop = max(
            0.0,
            previous_bar.volume_ratio -
            current_bar.volume_ratio,
        )

        volume_score = min(
            1.0,
            0.70 + volume_drop,
        )

        rejection_score = current_bar.close_ratio

        return min(
            1.0,
            (
                volume_score +
                rejection_score
            ) / 2
        )

    @staticmethod
    def upthrust(
        current_bar,
    ) -> float:

        volume_score = min(
            1.0,
            current_bar.volume_ratio,
        )

        spread_score = min(
            1.0,
            current_bar.spread_ratio,
        )

        rejection_score = (
            1.0 -
            current_bar.close_ratio
        )

        strength = (
            volume_score * 0.45 +
            spread_score * 0.25 +
            rejection_score * 0.30
        )

        return min(
            1.0,
            strength,
        )

    @staticmethod
    def shakeout(
        current_bar,
    ) -> float:

        volume_score = min(
            1.0,
            current_bar.volume_ratio,
        )

        spread_score = min(
            1.0,
            current_bar.spread_ratio,
        )

        rejection_score = current_bar.close_ratio

        strength = (
            volume_score * 0.45 +
            spread_score * 0.25 +
            rejection_score * 0.30
        )

        return min(
            1.0,
            strength,
        )