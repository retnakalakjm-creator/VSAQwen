"""Production-path audit for DEMAND_COMING_IN.

Analysis-only. Verifies collection, registry, dynamic weighting, scoring, and
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
from evidence.scoring import _score_bias
from evidence.weight import WeightCalculator
from metrics_engine import MetricsEngine
from models import EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOL = "HDFCBANK.NS"
TARGET = EvidenceCode.DEMAND_COMING_IN


def main() -> None:
    demand_source = inspect.getsource(collect_demand)
    engine_source = inspect.getsource(EvidenceEngine.collect)
    weight_source = inspect.getsource(WeightCalculator.calculate)

    registry_definition = EVIDENCE_LIBRARY.get(TARGET)

    metrics = MetricsEngine().calculate(
        daily_to_weekly(download_data(SYMBOL))
    )

    production_hits = 0
    candidate_bars = 0

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
        production_hits += sum(item.code == TARGET for item in result.evidence)

    print("DEMAND COMING IN PRODUCTION PATH AUDIT")
    print({
        "target": TARGET.name,
        "candidate_bars_replayed": candidate_bars,
        "actual_production_hits": production_hits,
        "collector_contains_target": "DEMAND_COMING_IN" in demand_source,
        "engine_collect_calls_demand": "self._collect_demand()" in engine_source,
        "weight_calculator_has_target_case": "EvidenceCode.DEMAND_COMING_IN" in weight_source,
        "registry_present": registry_definition is not None,
        "registry_weight": None if registry_definition is None else registry_definition.weight,
        "registry_strength": None if registry_definition is None else registry_definition.strength,
        "synthetic_scoring_weight_038": 0.38 * 0.90,
        "current_default_weight_if_emitted": 1.00,
        "production_path_status": (
            "NOT_READY_TARGET_NOT_COLLECTED"
            if production_hits == 0
            else "TARGET_COLLECTED"
        ),
        "notes": [
            "This audit does not modify collector, registry, weight, scoring, or aggregation logic.",
            "Weight 0.38 remains provisional and is not registered by this audit.",
        ],
    })

    baseline = _score_bias([])
    print("DEMAND COMING IN EMPTY_BIAS_CHECK")
    print({"empty_bias": baseline.name})


if __name__ == "__main__":
    main()
