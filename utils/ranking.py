from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence


def percentile_rank(
    value: float,
    sample: Sequence[float],
) -> float:
    """
    Return the percentile rank of a value.

    Returns
    -------
    float
        Percentile in the range [0.0, 1.0].
    """

    if not sample:
        return 0.0

    ordered = sorted(sample)

    rank = bisect_right(
        ordered,
        value,
    )
    
    return rank / len(ordered)