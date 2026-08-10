"""Read-only inventory of the current evidence model.

This diagnostic does not run market data, modify production logic, or change
any configuration. It reports the current EvidenceCode taxonomy, weighting
roles, aggregation groups, and the explicit phase mapping used by
``evidence.scoring._score_phase``.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow this script to be run directly from the tools directory:
#     python tools/inventory_evidence_model.py
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import config
from models import EvidenceCode


PHASE_MAPPING = {
    EvidenceCode.ACCUMULATION: "ACCUMULATION",
    EvidenceCode.REACCUMULATION: "REACCUMULATION",
    EvidenceCode.MARKUP: "MARKUP",
    EvidenceCode.DISTRIBUTION: "DISTRIBUTION",
    EvidenceCode.REDISTRIBUTION: "REDISTRIBUTION",
    EvidenceCode.MARKDOWN: "MARKDOWN",
}

BULLISH_CODES = {
    EvidenceCode.STOPPING_VOLUME,
    EvidenceCode.DEMAND_COMING_IN,
    EvidenceCode.INCREASING_DEMAND,
    EvidenceCode.HIDDEN_DEMAND,
    EvidenceCode.DEMAND_DRYING_UP,
    EvidenceCode.STRONG_UPTREND,
    EvidenceCode.WEAK_UPTREND,
    EvidenceCode.ACCUMULATION,
    EvidenceCode.REACCUMULATION,
    EvidenceCode.MARKUP,
    EvidenceCode.SPRING,
    EvidenceCode.TEST,
    EvidenceCode.SHAKEOUT,
    EvidenceCode.NO_SUPPLY,
    EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
}

BEARISH_CODES = {
    EvidenceCode.BUYING_CLIMAX,
    EvidenceCode.SUPPLY_COMING_IN,
    EvidenceCode.INCREASING_SUPPLY,
    EvidenceCode.HIDDEN_SUPPLY,
    EvidenceCode.SUPPLY_DRYING_UP,
    EvidenceCode.STRONG_DOWNTREND,
    EvidenceCode.WEAK_DOWNTREND,
    EvidenceCode.DISTRIBUTION,
    EvidenceCode.REDISTRIBUTION,
    EvidenceCode.MARKDOWN,
    EvidenceCode.UPTHRUST,
    EvidenceCode.NO_DEMAND,
    EvidenceCode.SELLING_CLIMAX,
    EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
}


def _role(code: EvidenceCode) -> str:
    roles = []
    if code in config.PRIMARY_VSA_CODES:
        roles.append("PRIMARY")
    if code in config.SUPPORTING_VSA_CODES:
        roles.append("SUPPORTING")
    if code in config.EFFORT_RESULT_CODES:
        roles.append("EFFORT_RESULT")
    if code in config.STRUCTURAL_CODES:
        roles.append("STRUCTURAL")
    return "+".join(roles) or "UNCLASSIFIED"


def _direction(code: EvidenceCode) -> str:
    if code in BULLISH_CODES:
        return "BULLISH"
    if code in BEARISH_CODES:
        return "BEARISH"
    return "NEUTRAL/CONTEXT"


def _weight(code: EvidenceCode) -> str:
    if code in config.SUPPLY_EVIDENCE_WEIGHTS:
        return str(config.SUPPLY_EVIDENCE_WEIGHTS[code])
    if code in config.DEMAND_EVIDENCE_WEIGHTS:
        return str(config.DEMAND_EVIDENCE_WEIGHTS[code])
    if code in config.EFFORT_EVIDENCE_WEIGHTS:
        return str(config.EFFORT_EVIDENCE_WEIGHTS[code])
    return "-"


def main() -> None:
    print("EVIDENCE MODEL INVENTORY")
    print("=" * 110)
    print(f"Total EvidenceCode values: {len(EvidenceCode)}")
    print()
    print(
        f"Aggregation modifiers: "
        f"primary+supporting={config.PRIMARY_SUPPORTING_MODIFIER}, "
        f"primary+effort_result={config.PRIMARY_EFFORT_RESULT_MODIFIER}, "
        f"primary+structural={config.PRIMARY_STRUCTURAL_MODIFIER}"
    )
    print(
        f"No-primary base weights: supporting={config.SUPPORTING_BASE_WEIGHT}, "
        f"effort_result={config.EFFORT_RESULT_BASE_WEIGHT}, "
        f"structural={config.STRUCTURAL_BASE_WEIGHT}"
    )
    print(f"Max combined event contribution: {config.MAX_COMBINED_EVENT_CONTRIBUTION}")
    print()
    print("code | direction | role | direct_weight | phase_mapping")
    print("-" * 110)

    for code in EvidenceCode:
        print(
            f"{code.value:40} | "
            f"{_direction(code):14} | "
            f"{_role(code):18} | "
            f"{_weight(code):13} | "
            f"{PHASE_MAPPING.get(code, '-')}"
        )

    print()
    print("PHASE SCORING")
    print("-" * 110)
    print("Phase score = sum(item.weight * item.strength) for explicit phase evidence.")
    print("Dominant phase = highest accumulated phase score.")
    print("No explicit phase evidence = UNKNOWN.")

    print()
    print("AGGREGATION PATH")
    print("-" * 110)
    print("1. Group evidence by (bar_index, direction).")
    print("2. Identify primary/supporting/effort-result/structural groups.")
    print("3. If primary exists, it is the anchor.")
    print("4. Supporting, effort-result, and structural evidence modify the anchor.")
    print("5. Without primary evidence, supporting/effort-result/structural evidence use reduced base weights.")
    print("6. Final event contribution is added to bullish or bearish aggregate score.")


if __name__ == "__main__":
    main()
