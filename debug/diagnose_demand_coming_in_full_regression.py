from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from evidence.scoring import _score_bias
from metrics_engine import MetricsEngine
from models import EvidenceCode
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS",
    "RELIANCE.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "INFY.NS",
    "TCS.NS",
    "SBIN.NS",
    "LT.NS",
)
TARGET = EvidenceCode.DEMAND_COMING_IN
EXPECTED_WEIGHT = 0.38


def main() -> None:
    failures: list[str] = []
    symbols_with_hits = 0
    total_target_hits = 0
    weighted_target_hits = 0
    target_bias_changes = 0
    all_biases = {"BEARISH": 0, "NEUTRAL": 0, "BULLISH": 0}

    for symbol in SYMBOLS:
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            symbol_hits = 0
            symbol_weighted = 0
            for index in range(20, len(metrics)):
                replay = metrics.iloc[: index + 1]
                trend = TrendAnalyzer().analyze(replay)
                engine = EvidenceEngine()
                result = engine.collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=tuple(trend.structure.structural_swings),
                    validation_metrics=replay,
                )
                target_items = [item for item in result.evidence if item.code == TARGET]
                if not target_items:
                    continue
                symbol_hits += len(target_items)
                symbol_weighted += sum(abs(item.weight - EXPECTED_WEIGHT) < 1e-12 for item in target_items)
                total_target_hits += len(target_items)
                weighted_target_hits += sum(abs(item.weight - EXPECTED_WEIGHT) < 1e-12 for item in target_items)
                bias = _score_bias(result.evidence)
                all_biases[bias.name] += 1

            if symbol_hits:
                symbols_with_hits += 1
            print(symbol, {"target_hits": symbol_hits, "target_weight_038": symbol_weighted})
        except Exception as exc:
            failures.append(f"{symbol}: {exc}")

    print("DEMAND COMING IN FULL REGRESSION AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_hits": symbols_with_hits,
        "target_hits": total_target_hits,
        "weighted_at_038": weighted_target_hits,
        "weight_integrity": total_target_hits == weighted_target_hits,
        "failures": failures,
        "bias_population_from_target_events": all_biases,
        "status": "PASS" if not failures and total_target_hits == weighted_target_hits else "FAIL",
    })


if __name__ == "__main__":
    main()
