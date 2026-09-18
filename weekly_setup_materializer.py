from __future__ import annotations

from background.qualification import PatternQualification
from scanner import ScannerCandidate
from weekly_setup import (
    WeeklySetup,
    WeeklySetupDirection,
    build_weekly_setup_id,
)


def materialize_production_weekly_setup(
    candidate: ScannerCandidate,
    *,
    symbol: str,
) -> WeeklySetup | None:
    """Convert one authoritative production candidate into a WeeklySetup.

    This is an adapter, not a new qualification layer. A setup is materialized
    only when the existing production ScannerCandidate is already actionable and
    persistently qualified. No WF7 shadow behavior, counterfactual evidence, or
    new threshold participates in the decision.

    Support/resistance zones, invalidation levels, and expiry policy remain
    intentionally unset because they have not been promoted as production
    WeeklySetup semantics.
    """

    clean_symbol = symbol.strip().upper()
    if not clean_symbol:
        raise ValueError("symbol must not be empty")

    if not candidate.actionable:
        return None

    qualification = candidate.qualification
    if qualification is PatternQualification.PERSISTENT_BULLISH:
        direction = WeeklySetupDirection.BULLISH
    elif qualification is PatternQualification.PERSISTENT_BEARISH:
        direction = WeeklySetupDirection.BEARISH
    else:
        return None

    signal_week = str(candidate.week or "").strip()
    if not signal_week:
        raise ValueError("actionable production candidate must have a signal week")

    return WeeklySetup(
        setup_id=build_weekly_setup_id(clean_symbol, signal_week, direction),
        symbol=clean_symbol,
        direction=direction,
        signal_week=signal_week,
        qualification=qualification,
        weekly_confidence=float(candidate.confidence),
        weekly_net_strength=float(candidate.net_strength),
        weekly_net_pressure=float(candidate.net_pressure),
        qualifying_evidence=tuple(candidate.qualifying_evidence),
        supporting_evidence=tuple(candidate.scoring_evidence),
    )


__all__ = ["materialize_production_weekly_setup"]
