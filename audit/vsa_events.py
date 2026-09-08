"""VSA event causality contract catalog.

This module is analysis-only. It documents the current production VSA event
recognition contracts so future calibration changes can be reviewed against a
stable baseline before modifying scoring or detector logic.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import pandas as pd


CURRENT_BAR = "current_bar"
RECOVERY_ANCHORED = "recovery_anchored"
CONFIRMATION_ANCHORED = "confirmation_anchored"
DIAGNOSTIC_ONLY = "diagnostic_only"
GATING = "gating"


@dataclass(frozen=True, slots=True)
class VSAEventContract:
    """Documented causality contract for one VSA event detector."""

    evidence_code: str
    module: str
    detector: str
    direction: str
    recognition_timing: str
    emitted_bar: str
    mandatory_requirements: tuple[str, ...]
    diagnostic_confirmations: tuple[str, ...]
    uses_future_bars: bool
    future_bar_policy: str
    source_documents: tuple[str, ...] = ()
    known_review_notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return a JSON/DataFrame friendly representation."""
        return asdict(self)


VSA_EVENT_CONTRACTS: tuple[VSAEventContract, ...] = (
    VSAEventContract(
        evidence_code="STOPPING_VOLUME",
        module="evidence.demand",
        detector="_collect_stopping_volume",
        direction="bullish",
        recognition_timing=CURRENT_BAR,
        emitted_bar="current candidate bar",
        mandatory_requirements=(
            "selling campaign",
            "bearish/down bar",
            "high volume",
            "above-average spread",
            "close not on weak/lower area",
        ),
        diagnostic_confirmations=(
            "very high volume",
            "wide spread",
            "volume increasing versus previous bar",
            "higher low versus previous bar",
        ),
        uses_future_bars=False,
        future_bar_policy="No forward bars are required; all predicates use current and previous/context bars only.",
        source_documents=(
            "docs/specifications/001_stopping_volume.md",
            "docs/PRIMARY_VSA_EVENT_MATRIX.md",
        ),
        known_review_notes=(
            "Confirmations are not gating in evaluate_detector; they are diagnostic unless promoted in a later PR.",
        ),
    ),
    VSAEventContract(
        evidence_code="SELLING_CLIMAX",
        module="evidence.demand",
        detector="_collect_selling_climax",
        direction="bullish",
        recognition_timing=CURRENT_BAR,
        emitted_bar="current candidate bar",
        mandatory_requirements=(
            "selling campaign",
            "bearish/down bar",
            "very high volume",
            "above-average spread",
        ),
        diagnostic_confirmations=(
            "wide spread",
            "strong close",
            "increasing volume versus previous bar",
        ),
        uses_future_bars=False,
        future_bar_policy="No forward bars are required; all predicates use current and previous/context bars only.",
        source_documents=("docs/PRIMARY_VSA_EVENT_MATRIX.md",),
        known_review_notes=(
            "Confirmations are not gating in evaluate_detector; they are diagnostic unless promoted in a later PR.",
        ),
    ),
    VSAEventContract(
        evidence_code="TEST",
        module="evidence.demand",
        detector="_collect_test",
        direction="bullish",
        recognition_timing=CURRENT_BAR,
        emitted_bar="current candidate bar",
        mandatory_requirements=(
            "selling campaign",
            "bearish/down bar",
            "low volume",
            "narrow spread",
            "no strong downtrend contradiction",
        ),
        diagnostic_confirmations=(
            "volume decreasing versus previous bar",
            "strong close",
            "higher low versus previous bar",
        ),
        uses_future_bars=False,
        future_bar_policy="No forward bars are required; all predicates use current and previous/context bars only.",
        source_documents=(
            "docs/specifications/003_test.md",
            "docs/PRIMARY_VSA_EVENT_MATRIX.md",
        ),
        known_review_notes=(
            "Confirmations are not gating in evaluate_detector; they are diagnostic unless promoted in a later PR.",
        ),
    ),
    VSAEventContract(
        evidence_code="NO_SUPPLY",
        module="evidence.demand",
        detector="_collect_no_supply",
        direction="bullish",
        recognition_timing=CURRENT_BAR,
        emitted_bar="current candidate bar",
        mandatory_requirements=(
            "bearish environment predicate currently named Bullish Environment in source",
            "bearish/down bar",
            "low volume",
            "narrow spread",
        ),
        diagnostic_confirmations=(
            "weak spread",
            "volume decreasing versus previous bar",
            "weak selling result / weak close",
        ),
        uses_future_bars=False,
        future_bar_policy="No forward bars are required; all predicates use current and previous/context bars only.",
        source_documents=(
            "docs/specifications/005_no_supply.md",
            "docs/PRIMARY_VSA_EVENT_MATRIX.md",
        ),
        known_review_notes=(
            "Source label says Bullish Environment but calls ctx.is_bearish_environment(); review naming separately.",
            "Confirmations are not gating in evaluate_detector; they are diagnostic unless promoted in a later PR.",
        ),
    ),
    VSAEventContract(
        evidence_code="INCREASING_DEMAND",
        module="evidence.demand",
        detector="_collect_increasing_demand",
        direction="bullish",
        recognition_timing=CURRENT_BAR,
        emitted_bar="current candidate bar",
        mandatory_requirements=(
            "bullish/up bar",
            "high volume",
            "above-average spread",
            "volume increasing versus previous bar",
        ),
        diagnostic_confirmations=(),
        uses_future_bars=False,
        future_bar_policy="No forward bars are required; all predicates use current and previous/context bars only.",
        source_documents=(
            "docs/INCREASING_DEMAND_AUDIT.md",
            "docs/PRIMARY_VSA_EVENT_MATRIX.md",
        ),
    ),
    VSAEventContract(
        evidence_code="SHAKEOUT",
        module="evidence.demand / evidence.campaign",
        detector="_collect_shakeout / validate_shakeout",
        direction="bullish",
        recognition_timing=RECOVERY_ANCHORED,
        emitted_bar="recovery bar, with test_index and recovery_index attached",
        mandatory_requirements=(
            "candidate bearish/down bar",
            "selling pressure present",
            "wide spread",
            "very high volume",
            "lower low versus previous bar",
            "valid low-volume/low-spread test after candidate",
            "valid recovery after test",
        ),
        diagnostic_confirmations=(),
        uses_future_bars=False,
        future_bar_policy=(
            "Validation may inspect bars after the original shakeout candidate, but production collection slices validation_metrics "
            "through the current recovery bar only. The event is therefore delayed-recognition, not candidate-bar look-ahead."
        ),
        source_documents=(
            "docs/specifications/002_shakeout.md",
            "docs/PRIMARY_VSA_EVENT_MATRIX.md",
        ),
        known_review_notes=(
            "Do not emit SHAKEOUT on the original candidate bar unless a future PR explicitly models pending events.",
        ),
    ),
    VSAEventContract(
        evidence_code="SPRING",
        module="evidence.spring",
        detector="collect_spring / detect_spring_candidate / validate_spring",
        direction="bullish",
        recognition_timing=CONFIRMATION_ANCHORED,
        emitted_bar="confirmation/recovery bar, with test_index and recovery_index attached",
        mandatory_requirements=(
            "prior structural support touches",
            "controlled support penetration",
            "candidate recovery back near support",
            "valid low-effort test after candidate",
            "bullish confirmation after test",
        ),
        diagnostic_confirmations=(),
        uses_future_bars=False,
        future_bar_policy=(
            "Validation may inspect bars after the original spring candidate, but production collection slices metrics "
            "through the current confirmation bar only. The event is therefore delayed-recognition, not candidate-bar look-ahead."
        ),
        source_documents=(
            "docs/specifications/004_spring.md",
            "docs/PRIMARY_VSA_EVENT_MATRIX.md",
        ),
        known_review_notes=(
            "Same-bar UPTHRUST or BUYING_CLIMAX reduces Spring quality rather than rejecting the event.",
        ),
    ),
    VSAEventContract(
        evidence_code="BUYING_CLIMAX",
        module="evidence.supply",
        detector="_collect_buying_climax",
        direction="bearish",
        recognition_timing=CURRENT_BAR,
        emitted_bar="current candidate bar",
        mandatory_requirements=(
            "buying campaign",
            "bullish/up bar",
            "very high volume",
            "above-average spread",
        ),
        diagnostic_confirmations=(
            "wide spread",
            "weak close",
            "increasing volume versus previous bar",
        ),
        uses_future_bars=False,
        future_bar_policy="No forward bars are required; all predicates use current and previous/context bars only.",
        source_documents=(
            "docs/BUYING_CLIMAX_AUDIT.md",
            "docs/PRIMARY_VSA_EVENT_MATRIX.md",
        ),
        known_review_notes=(
            "Confirmations are not gating in evaluate_detector; they are diagnostic unless promoted in a later PR.",
        ),
    ),
    VSAEventContract(
        evidence_code="UPTHRUST",
        module="evidence.supply",
        detector="_collect_upthrust",
        direction="bearish",
        recognition_timing=CURRENT_BAR,
        emitted_bar="current candidate bar",
        mandatory_requirements=(
            "buying campaign",
            "bullish/up bar",
            "very high volume",
            "above-average spread",
        ),
        diagnostic_confirmations=(
            "wide spread",
            "weak close",
            "lower close than previous bar",
        ),
        uses_future_bars=False,
        future_bar_policy="No forward bars are required; all predicates use current and previous/context bars only.",
        source_documents=(
            "docs/UPTHRUST_AUDIT.md",
            "docs/PRIMARY_VSA_EVENT_MATRIX.md",
        ),
        known_review_notes=(
            "Confirmations are not gating in evaluate_detector; they are diagnostic unless promoted in a later PR.",
        ),
    ),
    VSAEventContract(
        evidence_code="NO_DEMAND",
        module="evidence.supply",
        detector="_collect_no_demand",
        direction="bearish",
        recognition_timing=CURRENT_BAR,
        emitted_bar="current candidate bar",
        mandatory_requirements=(
            "bullish environment",
            "bullish/up bar",
            "low volume",
            "narrow spread",
        ),
        diagnostic_confirmations=(
            "volume decreasing versus previous bar",
            "weak close",
        ),
        uses_future_bars=False,
        future_bar_policy="No forward bars are required; all predicates use current and previous/context bars only.",
        source_documents=(
            "docs/NO_DEMAND_AUDIT.md",
            "docs/PRIMARY_VSA_EVENT_MATRIX.md",
        ),
        known_review_notes=(
            "Confirmations are not gating in evaluate_detector; they are diagnostic unless promoted in a later PR.",
            "NO_DEMAND_AUDIT.md lists evidence/demand.py::_collect_no_demand, but current source defines it in evidence/supply.py.",
        ),
    ),
    VSAEventContract(
        evidence_code="SUPPLY_COMING_IN",
        module="evidence.supply",
        detector="_collect_supply_coming_in",
        direction="bearish",
        recognition_timing=CURRENT_BAR,
        emitted_bar="current candidate bar",
        mandatory_requirements=(
            "buying campaign",
            "down bar",
            "high volume",
            "above-average spread",
            "weak close",
            "volume increasing versus previous bar",
        ),
        diagnostic_confirmations=(),
        uses_future_bars=False,
        future_bar_policy="No forward bars are required; all predicates use current and previous/context bars only.",
        source_documents=(
            "docs/SUPPLY_COMING_IN_AUDIT.md",
            "docs/PRIMARY_VSA_EVENT_MATRIX.md",
        ),
    ),
    VSAEventContract(
        evidence_code="ABSORPTION",
        module="evidence.absorption",
        detector="collect_absorption",
        direction="bullish/contextual",
        recognition_timing=CURRENT_BAR,
        emitted_bar="current candidate bar",
        mandatory_requirements=(
            "bearish/down bar",
            "high volume",
            "above-average spread",
            "upper/strong close",
            "lower low versus previous bar",
        ),
        diagnostic_confirmations=(),
        uses_future_bars=False,
        future_bar_policy="No forward bars are required; all predicates use current and previous/context bars only.",
        source_documents=(
            "docs/ABSORPTION_AUDIT.md",
            "docs/PRIMARY_VSA_EVENT_MATRIX.md",
        ),
        known_review_notes=(
            "ABSORPTION_AUDIT.md and current code show a production-connected non-scoring detector through collect_demand().",
            "PRIMARY_VSA_EVENT_MATRIX.md still contains stale no-production-detector wording for ABSORPTION; resolve in a documentation cleanup PR.",
        ),
    ),
)


def iter_vsa_event_contracts() -> tuple[VSAEventContract, ...]:
    """Return all documented VSA event contracts."""
    return VSA_EVENT_CONTRACTS


def vsa_event_contract_frame(
    contracts: Iterable[VSAEventContract] = VSA_EVENT_CONTRACTS,
) -> pd.DataFrame:
    """Return the contract catalog as a DataFrame for review/export."""
    return pd.DataFrame([contract.as_dict() for contract in contracts])


def contracts_by_code() -> dict[str, VSAEventContract]:
    """Return contracts keyed by evidence code."""
    return {contract.evidence_code: contract for contract in VSA_EVENT_CONTRACTS}


def non_causal_contracts() -> tuple[VSAEventContract, ...]:
    """Return contracts currently marked as using unavailable future bars."""
    return tuple(contract for contract in VSA_EVENT_CONTRACTS if contract.uses_future_bars)


__all__ = [
    "CONFIRMATION_ANCHORED",
    "CURRENT_BAR",
    "DIAGNOSTIC_ONLY",
    "GATING",
    "RECOVERY_ANCHORED",
    "VSAEventContract",
    "VSA_EVENT_CONTRACTS",
    "contracts_by_code",
    "iter_vsa_event_contracts",
    "non_causal_contracts",
    "vsa_event_contract_frame",
]
