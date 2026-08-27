"""Effort vs Result evidence collector."""

from __future__ import annotations

from models import BackgroundContext, Evidence, EvidenceCode
from .helpers import EvidenceCollector, add_evidence
from .rules import (
    is_high_volume,
    is_low_volume,
    is_narrow_spread,
    is_neutral_close,
    is_strong_close,
    is_weak_close,
    is_wide_spread,
)


def collect_effort(ctx: BackgroundContext) -> list[Evidence]:
    """Collect contextual Effort vs Result evidence."""
    evidence: list[Evidence] = []

    _detect_effort_greater_than_result(ctx, evidence)
    _detect_result_greater_than_effort(ctx, evidence)

    return evidence


def _detect_effort_greater_than_result(
    ctx: BackgroundContext,
    evidence: list[Evidence],
) -> None:
    """Large effort producing little result."""
    last = ctx.current

    if not is_high_volume(last):
        return
    if not is_narrow_spread(last):
        return
    if not (is_weak_close(last) or is_neutral_close(last)):
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


__all__ = ["EvidenceCollector", "collect_effort"]
