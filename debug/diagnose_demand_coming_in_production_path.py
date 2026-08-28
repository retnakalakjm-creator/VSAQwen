"""Production-path audit for DEMAND_COMING_IN.

Analysis-only. Verifies collection, registry, weighting, scoring, and
final aggregation touchpoints without modifying production behavior.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import (
    COL_CLOSE_POSITION,
    COL_DIRECTION,
    COL_SPREAD_CLASS,
    COL_VOLUME_CLASS,
)
from evidence.demand import collect_demand
from evidence.engine import EvidenceEngine
from evidence.evidence_registry import EVIDENCE_LIBRARY
from evidence.helpers import add_evidence
from evidence.scoring import _score_bias
from evidence.weight import WeightCalculator
from metrics_engine import MetricsEngine
from models import BackgroundContext, EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOL = "HDFCBANK.NS"
TARGET = EvidenceCode.DEMAND_COMING_IN


def main() -> None:
    engine_source = inspect.getsource(EvidenceEngine.collect)
    helper_source = inspect.getsource(add_evidence)
    registry_definition = EVIDENCE_LIBRARY.get(TARGET)

    metrics = MetricsEngine().calculate(
        daily_to_weekly(download_data(SYMBOL))
    )

    production_hits = 0
    candidate_bars = 0
    target_weights: list[float] = []

    for index in range(20, len(metrics)):
        row = metrics.iloc[index]
        if not (
            int(row[COL_DIRECTION]) == -1
            and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
            and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
            and int(row[COL_CLOSE_POSITION]) >= 2
        ):
            continue

        candidate_bars += 1
        replay = metrics.iloc[: index + 1]
        replay_trend = TrendAnalyzer().analyze(replay)
        engine = EvidenceEngine()
        result = engine.collect(
            metrics=replay,
            trend=replay_trend,
            structural_swings=tuple(replay_trend.structure.structural_swings),
            validation_metrics=replay,
        )
        hits = [item for item in result.evidence if item.code == TARGET]
        production_hits += len(hits)
        target_weights.extend(item.weight for item in hits)

    collector_target_present = production_hits > 0
    helper_target_case = "EvidenceCode.DEMAND_COMING_IN" in helper_source
    observed_weight_ok = bool(target_weights) and all(
        abs(weight - 0.38) < 1e-12 for weight in target_weights
    )

    print("DEMAND COMING IN PRODUCTION PATH AUDIT")
    print({
        "target": TARGET.name,
        "candidate_bars_replayed": candidate_bars,
        "actual_production_hits": production_hits,
        "collector_contains_target": collector_target_present,
        "engine_collect_calls_demand": "self._collect_demand()" in engine_source,
        "weight_calculator_has_target_case": "EvidenceCode.DEMAND_COMING_IN" in inspect.getsource(WeightCalculator.calculate),
        "helper_weight_path_has_target_case": helper_target_case,
        "observed_production_weight_038": observed_weight_ok,
        "observed_target_weights": sorted(set(target_weights)),
        "registry_present": registry_definition is not None,
        "registry_weight": None if registry_definition is None else registry_definition.weight,
        "registry_strength": None if registry_definition is None else registry_definition.strength,
        "synthetic_scoring_weight_038": 0.38 * 0.90,
        "production_path_status": (
            "TARGET_COLLECTED_AND_WEIGHTED_038"
            if production_hits > 0 and helper_target_case and observed_weight_ok
            else "NOT_READY"
        ),
        "notes": [
            "DEMAND_COMING_IN uses the audited 0.38 helper-level weight path; WeightCalculator is intentionally unchanged.",
            "Registry weight 1.0 remains the profile default and is not the emitted Evidence.weight.",
        ],
    })

    baseline = _score_bias([])
    print("DEMAND COMING IN EMPTY_BIAS_CHECK")
    print({"empty_bias": baseline.name})


if __name__ == "__main__":
    main()
