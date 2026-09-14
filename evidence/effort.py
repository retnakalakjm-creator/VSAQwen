"""Effort vs Result evidence collector."""

from __future__ import annotations

from models import BackgroundContext, Evidence, EvidenceCode
from .absorption import collect_absorption
from .helpers import EvidenceCollector, add_evidence
from .high_volume_reversal import collect_high_volume_reversal
from .rules import (
    is_average_spread,
    is_below_average_spread,
    is_high_volume,
    is_low_volume,
    is_narrow_spread,
    is_neutral_close,
    is_strong_close,
    is_very_high_volume,
    is_weak_close,
    is_wide_spread,
)


def collect_effort(ctx: BackgroundContext) -> list[Evidence]:
    """Collect contextual Effort vs Result evidence.

    Effort/Result, Absorption, and High Volume Reversal remain
    production-visible read-only evidence: these collectors may emit evidence
    for API/frontend review visibility, but scanner scoring, ranking,
    qualification, actionability, alerts, and orders continue to exclude their
    read-only codes.
    """
    evidence: list[Evidence] = []

    _detect_effort_greater_than_result(ctx, evidence)
    _detect_result_greater_than_effort(ctx, evidence)
    evidence.extend(collect_absorption(ctx))
    evidence.extend(collect_high_volume_reversal(ctx))

    return evidence


def _detect_effort_greater_than_result(
    ctx: BackgroundContext,
    evidence: list[Evidence],
) -> None:
    """Large effort producing little result.

    This gate preserves the original high-volume narrow-result profile and adds
    the newer calibration for very-high-volume bars that produced muted downside.
    It is still read-only evidence and has no scoring weight.
    """
    last = ctx.current

    if not (is_high_volume(last) or is_very_high_volume(last)):
        return
    if not (_has_narrow_or_normal_spread(last) or _has_muted_downside_result(ctx)):
        return
    if not (is_weak_close(last) or is_neutral_close(last) or _has_muted_downside_result(ctx)):
        return

    add_evidence(
        evidence=evidence,
        ctx=ctx,
        code=EvidenceCode.EFFORT_GT_RESULT,
    )


def _detect_result_greater_than_effort(
    ctx: BackgroundContext,
    evidence: list[Evidence],
) -> None:
    """Good result produced with little effort."""
    last = ctx.current

    if not is_low_volume(last):
        return
    if not is_wide_spread(last):
        return
    if not is_strong_close(last):
        return

    add_evidence(
        evidence=evidence,
        ctx=ctx,
        code=EvidenceCode.RESULT_GT_EFFORT,
    )


def _has_narrow_or_normal_spread(bar) -> bool:
    return (
        is_narrow_spread(bar)
        or is_below_average_spread(bar)
        or is_average_spread(bar)
        or float(getattr(bar, "spread_ratio", 1.0)) <= 1.1
    )


def _has_muted_downside_result(ctx: BackgroundContext) -> bool:
    last = ctx.current
    previous = getattr(ctx, "previous", None)
    if float(getattr(last, "close_ratio", 0.5)) >= 0.35:
        return True
    if previous is None:
        return False

    previous_close = float(getattr(previous, "close_price", getattr(last, "prev_close", 0.0)))
    if previous_close <= 0.0:
        return False

    close_price = float(getattr(last, "close_price", previous_close))
    downside_pct = max(0.0, ((previous_close - close_price) / previous_close) * 100.0)
    return downside_pct <= 2.5


__all__ = ["EvidenceCollector", "collect_effort"]