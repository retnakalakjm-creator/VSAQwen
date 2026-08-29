from __future__ import annotations

from bisect import bisect_right
from collections.abc import Sequence
from line_profiler import profile

@profile
def percentile_rank(
    value: float,
    sample: Sequence[float],
) -> float:
    """
    Return the percentile rank of a value.

    The sample may be in any order.
    """

    if not sample:
        return 0.0

    ordered = sorted(sample)
    return percentile_rank_sorted(value, ordered)


def percentile_rank_sorted(
    value: float,
    ordered_sample: Sequence[float],
) -> float:
    """
    Return the percentile rank of a value against an already sorted sample.

    This avoids repeatedly sorting the same historical sample when several
    percentile components are evaluated from the same immutable snapshot.
    """

    if not ordered_sample:
        return 0.0

    rank = bisect_right(ordered_sample, value)
    return rank / len(ordered_sample)
