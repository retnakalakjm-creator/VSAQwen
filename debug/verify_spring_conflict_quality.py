"""Verify Spring conflict quality on the 13 known production Spring bars."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer

PRODUCTION_SPRINGS = {
    "BHARTIARTL.NS": (541, 698),
    "RELIANCE.NS": (1530,),
    "HDFCBANK.NS": (248, 290, 301, 836, 1055, 1195),
    "ICICIBANK.NS": (100, 928),
    "INFY.NS": (1269,),
    "SBIN.NS": (256,),
}
CONFLICT_CODES = {"UPTHRUST", "BUYING_CLIMAX"}


def code_name(item) -> str:
    return str(item.code).split(".")[-1].upper()


def main() -> None:
    rows: list[dict] = []
    failures: list[dict] = []

    for symbol, bars in PRODUCTION_SPRINGS.items():
        try:
            metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
            trend_analyzer = TrendAnalyzer()
            engine = EvidenceEngine()

            for index in bars:
                replay = metrics.iloc[: index + 1]
                trend = trend_analyzer.analyze(replay)
                structural_swings = tuple(trend.structure.structural_swings)
                result = engine.collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=structural_swings,
                    validation_metrics=replay,
                )
                springs = [x for x in result.evidence if code_name(x) == "SPRING"]
                conflicts = sorted(
                    {
                        code_name(x)
                        for x in result.evidence
                        if x.bar_index == index and code_name(x) in CONFLICT_CODES
                    }
                )
                for spring in springs:
                    rows.append(
                        {
                            "symbol": symbol,
                            "bar_index": index,
                            "spring_quality": spring.quality,
                            "spring_weight": spring.weight,
                            "same_bar_conflicts": conflicts,
                        }
                    )
        except Exception as exc:
            failures.append({"symbol": symbol, "error": repr(exc)})

    reduced = [r for r in rows if r["spring_quality"] < 1.0]
    unchanged = [r for r in rows if r["spring_quality"] == 1.0]

    print("SPRING CONFLICT QUALITY VERIFICATION")
    print(
        {
            "expected_springs": sum(len(v) for v in PRODUCTION_SPRINGS.values()),
            "verified_springs": len(rows),
            "quality_reduced": len(reduced),
            "quality_unchanged": len(unchanged),
            "failures": failures,
        }
    )
    print("SPRING CONFLICT QUALITY EVENTS")
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
