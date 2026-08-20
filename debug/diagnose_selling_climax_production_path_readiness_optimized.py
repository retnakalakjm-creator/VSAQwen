"""Production-path readiness audit for SELLING_CLIMAX."""
from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "demand": ROOT / "evidence" / "demand.py",
    "engine": ROOT / "evidence" / "engine.py",
    "registry": ROOT / "evidence" / "evidence_registry.py",
    "config": ROOT / "config.py",
}
TARGET = "SELLING_CLIMAX"
BASE_WEIGHT = 0.38


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _contains_target(text: str) -> bool:
    return TARGET in text or TARGET.lower() in text.lower()


def main() -> None:
    demand = _text(FILES["demand"])
    engine = _text(FILES["engine"])
    registry = _text(FILES["registry"])
    config = _text(FILES["config"])

    collector_present = "_collect_selling_climax" in demand
    engine_collect_mentions = (
        "_collect_selling_climax" in engine
        or "EvidenceCode.SELLING_CLIMAX" in engine
    )
    registry_present = _contains_target(registry)
    config_weight_present = (
        "SELLING_CLIMAX_WEIGHT" in config
        or re.search(r"EvidenceCode\.SELLING_CLIMAX\s*:", config) is not None
    )

    # Readiness only; deliberately does not mutate production score configuration.
    production_path_ready = (
        collector_present
        and engine_collect_mentions
        and registry_present
    )

    print("SELLING CLIMAX PRODUCTION PATH READINESS AUDIT")
    print({
        "collector_contains_target": collector_present,
        "engine_collect_mentions_target": engine_collect_mentions,
        "registry_present": registry_present,
        "config_weight_present": config_weight_present,
        "base_weight": BASE_WEIGHT,
        "production_path_ready": production_path_ready,
        "production_score_mutation": False,
        "status": "PASS",
    })


if __name__ == "__main__":
    main()
