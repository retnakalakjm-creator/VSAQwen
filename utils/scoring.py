from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from line_profiler import profile


@dataclass(slots=True, frozen=True)
class ScoreBand:

    threshold: float

    score: float


def band_score(
    value: float,
    bands: Sequence[ScoreBand],
) -> float:
    """
    Return the first matching score.

    Bands must be ordered from highest threshold
to lowest threshold.
    """

    for band in bands:

        if value >= band.threshold:
            return band.score

    return 0.0


@dataclass(slots=True, frozen=True)
class ScoreComponent:
    """
    One weighted contribution to a final score.
    """

    value: float

    weight: float


@profile
def combine_scores(
    components: Sequence[ScoreComponent],
) -> float:
    """
    Combine weighted score components into a
    normalized score in the range [0.0, 1.0].
    """

    if not components:
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0

    for component in components:
        total_weight += component.weight
        weighted_sum += component.value * component.weight

    if total_weight <= 0:
        return 0.0

    return min(
        weighted_sum / total_weight,
        1.0,
    )


def component(
    value: float,
    weight: float,
) -> ScoreComponent:
    """
    Convenience helper for creating score components.
    """

    return ScoreComponent(
        value=value,
        weight=weight,
    )
