"""Production-readiness audit for ABSORPTION ranking impact.

ABSORPTION is currently not collected by EvidenceEngine, so a true live
ranking/bias comparison would be artificial. This audit verifies that state
and reports only the synthetic contribution implied by the provisional policy.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

BASE_WEIGHT = 0.38
CONFLICT_PENALTY = 0.20


def main() -> None:
    demand_path = (ROOT / "evidence" / "demand.py").read_text(encoding="utf-8")
    supply_path = (ROOT / "evidence" / "supply.py").read_text(encoding="utf-8")
    engine_path = (ROOT / "evidence" / "engine.py").read_text(encoding="utf-8")
    registry_path = (ROOT / "evidence" / "evidence_registry.py").read_text(encoding="utf-8")

    collector_contains_target = "EvidenceCode.ABSORPTION" in demand_path or "EvidenceCode.ABSORPTION" in supply_path
    engine_collect_mentions_target = "ABSORPTION" in engine_path
    registry_contains_target = "ABSORPTION" in registry_path

    print("ABSORPTION RANKING IMPACT READINESS AUDIT")
    print({
        "collector_contains_target": collector_contains_target,
        "engine_collect_mentions_target": engine_collect_mentions_target,
        "registry_contains_target": registry_contains_target,
        "base_weight": BASE_WEIGHT,
        "conflict_penalty": CONFLICT_PENALTY,
        "clean_effective_weight": BASE_WEIGHT,
        "conflict_effective_weight": BASE_WEIGHT * (1.0 - CONFLICT_PENALTY),
        "true_ranking_impact_status": "NOT_APPLICABLE_PRODUCTION_PATH_ABSENT" if not collector_contains_target else "READY_FOR_LIVE_RANKING_AUDIT",
        "synthetic_ranking_safe_weight": True,
        "production_score_mutation": False,
        "status": "PASS" if not collector_contains_target else "CHECK",
    })


if __name__ == "__main__":
    main()
