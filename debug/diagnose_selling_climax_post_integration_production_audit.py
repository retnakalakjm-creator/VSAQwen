"""Analysis-only post-integration audit for SELLING_CLIMAX production wiring."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_DIRECTION, COL_SPREAD_CLASS, COL_VOLUME_CLASS
from evidence.engine import EvidenceEngine
from evidence.campaign import has_selling_campaign
from metrics_engine import MetricsEngine
from models import EvidenceCode, SpreadClass, VolumeClass
from trend import TrendAnalyzer

SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
EXPECTED_WEIGHT = 0.38
FORWARD_BARS = 8


def _cheap_candidate(row) -> bool:
    return (
        int(row[COL_DIRECTION]) == -1
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.VERY_HIGH
        and SpreadClass(int(row[COL_SPREAD_CLASS])) >= SpreadClass.ABOVE_AVERAGE
    )


def _audit_symbol(symbol: str) -> dict:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
    out = {
        "symbol": symbol,
        "cheap_candidates": 0,
        "engine_replays": 0,
        "production_emissions": 0,
        "wrong_weight": 0,
        "duplicate_emissions": 0,
        "score_mutation_failures": 0,
        "campaign_mismatch": 0,
        "errors": [],
    }

    for index in range(21, len(metrics) - FORWARD_BARS):
        row = metrics.iloc[index]
        if not _cheap_candidate(row):
            continue
        out["cheap_candidates"] += 1

        replay = metrics.iloc[: index + 1]
        try:
            trend = TrendAnalyzer().analyze(replay)
            engine = EvidenceEngine()
            result = engine.collect(
                metrics=replay,
                trend=trend,
                structural_swings=tuple(trend.structure.structural_swings),
                validation_metrics=replay,
            )
            out["engine_replays"] += 1

            emitted = [e for e in result.evidence if e.code == EvidenceCode.SELLING_CLIMAX]
            if has_selling_campaign(engine._ctx):
                if not emitted:
                    out["campaign_mismatch"] += 1
                    continue

            if len(emitted) > 1:
                out["duplicate_emissions"] += 1
                continue
            if not emitted:
                continue

            out["production_emissions"] += 1
            item = emitted[0]
            if item.weight is None or abs(float(item.weight) - EXPECTED_WEIGHT) > 1e-9:
                out["wrong_weight"] += 1

            matching_bar = [
                e for e in result.evidence
                if e.code == EvidenceCode.SELLING_CLIMAX
                and int(e.bar_index) == int(row.name)
            ]
            if len(matching_bar) != 1:
                out["score_mutation_failures"] += 1

        except Exception as exc:
            out["errors"].append(repr(exc))

    return out


def main() -> None:
    results: list[dict] = []
    failures: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(4, len(SYMBOLS))) as executor:
        futures = {executor.submit(_audit_symbol, symbol): symbol for symbol in SYMBOLS}
        for future, symbol in futures.items():
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    cheap = sum(x["cheap_candidates"] for x in results)
    replays = sum(x["engine_replays"] for x in results)
    emissions = sum(x["production_emissions"] for x in results)
    wrong_weight = sum(x["wrong_weight"] for x in results)
    duplicates = sum(x["duplicate_emissions"] for x in results)
    score_failures = sum(x["score_mutation_failures"] for x in results)
    campaign_mismatch = sum(x["campaign_mismatch"] for x in results)
    errors = sum(len(x["errors"]) for x in results)

    print("SELLING CLIMAX POST-INTEGRATION PRODUCTION AUDIT")
    print({
        "symbols_requested": len(SYMBOLS),
        "symbols_with_results": len(results),
        "cheap_candidates": cheap,
        "engine_replays": replays,
        "production_emissions": emissions,
        "expected_weight": EXPECTED_WEIGHT,
        "wrong_weight": wrong_weight,
        "duplicate_emissions": duplicates,
        "score_mutation_failures": score_failures,
        "campaign_mismatch": campaign_mismatch,
        "errors": errors,
        "failures": failures,
        "status": "PASS" if not failures and errors == 0 and wrong_weight == 0 and duplicates == 0 and score_failures == 0 else "FAIL",
    })

    print("SELLING CLIMAX POST-INTEGRATION BY_SYMBOL")
    for item in sorted(results, key=lambda x: x["symbol"]):
        print({
            key: value
            for key, value in item.items()
            if key != "errors"
        } | {"errors": item["errors"]})


if __name__ == "__main__":
    main()
