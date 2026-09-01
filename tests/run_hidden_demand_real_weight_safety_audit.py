from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.columns import COL_CLOSE_POSITION, COL_DIRECTION, COL_VOLUME_CLASS
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection, VolumeClass
from professional.scoring_engine import ProfessionalScoringEngine
from trend import TrendAnalyzer
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS

HORIZONS = (3, 5, 10)
PROMOTED_CONTEXTS = {("healthy", "up"), ("unknown", "range")}
WEIGHTS = (0.00, 0.10, 0.15, 0.20, 0.25, 0.30)


def _is_hidden_demand(row) -> bool:
    return (
        Direction(int(row[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(row[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and ClosePosition(int(row[COL_CLOSE_POSITION])) >= ClosePosition.UPPER
    )


def _synthetic_hidden_demand(row, index: int) -> Evidence:
    week = row.get("week_beginning")
    return Evidence(
        code=EvidenceCode.HIDDEN_DEMAND,
        category=EvidenceCategory.DEMAND,
        direction=EvidenceDirection.BULLISH,
        strength=1.0,
        weight=1.0,
        observation="Counterfactual HIDDEN_DEMAND audit event",
        description="Research-only synthetic event; not a production collector output.",
        bar_index=index,
        week_beginning="" if week is None else str(week),
    )


def _counterfactual(
    trend,
    evidence,
    weight: float,
) -> tuple[float, float, float]:
    scorer = ProfessionalScoringEngine()
    trend_score = scorer._score_trend(trend)
    supply_score = scorer._score_supply(evidence)
    demand_score = scorer._score_demand(evidence)
    effort_score = scorer._score_effort(evidence)
    demand_score = min(demand_score + weight, 1.0)
    strength = scorer._score_strength(
        trend_score,
        demand_score,
        supply_score,
        effort_score,
    )
    weakness = scorer._score_weakness(
        trend_score,
        demand_score,
        supply_score,
        effort_score,
    )
    from model import ProfessionalScore
    confidence = scorer._measure_confidence(
        ProfessionalScore(
            trend=trend_score,
            supply=supply_score,
            demand=demand_score,
            effort=effort_score,
            strength=strength,
            weakness=weakness,
            confidence=0.0,
        )
    )
    return strength, weakness, confidence


def _audit_symbol(symbol: str, sample_bars: int) -> dict:
    daily = __import__("data").download_data(symbol)
    weekly = __import__("data").daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    evidence_engine = EvidenceEngine()
    scorer = ProfessionalScoringEngine()
    totals = {
        weight: {"selected": 0, "strength_change": [], "confidence_change": []}
        for weight in WEIGHTS
    }
    max_age = max(HORIZONS)
    start = max(20, len(metrics) - sample_bars - max_age)

    for index in range(start, len(metrics) - max_age):
        row = metrics.iloc[index]
        if not _is_hidden_demand(row):
            continue
        trend = TrendAnalyzer().analyze(metrics.iloc[: index + 1].copy())
        current = evidence_engine.collect(
            metrics=metrics.iloc[: index + 1].copy(),
            trend=trend,
            structural_swings=list(trend.structure.structural_swings),
        )
        selected = (
            trend.structure.state.value,
            trend.structure.direction.value,
        ) in PROMOTED_CONTEXTS
        if not selected:
            continue
        augmented = type(current)(
            context=current.context,
            evidence=current.evidence + (_synthetic_hidden_demand(row, index),),
        )
        baseline_strength = scorer._score_strength(
            scorer._score_trend(trend),
            scorer._score_demand(current),
            scorer._score_supply(current),
            scorer._score_effort(current),
        )
        baseline_confidence = scorer._measure_confidence(
            __import__("model").ProfessionalScore(
                trend=scorer._score_trend(trend),
                supply=scorer._score_supply(current),
                demand=scorer._score_demand(current),
                effort=scorer._score_effort(current),
                strength=baseline_strength,
                weakness=scorer._score_weakness(
                    scorer._score_trend(trend),
                    scorer._score_demand(current),
                    scorer._score_supply(current),
                    scorer._score_effort(current),
                ),
                confidence=0.0,
            )
        )
        for weight in WEIGHTS:
            strength, _, confidence = _counterfactual(trend, augmented, weight)
            totals[weight]["selected"] += 1
            totals[weight]["strength_change"].append(strength - baseline_strength)
            totals[weight]["confidence_change"].append(confidence - baseline_confidence)

    return {"symbol": symbol, "totals": totals}


def main() -> None:
    parser = argparse.ArgumentParser(description="HIDDEN_DEMAND counterfactual production-formula weight safety audit.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--symbols", nargs="+", default=None)
    args = parser.parse_args()
    if args.sample_bars <= max(HORIZONS):
        raise ValueError("--sample-bars must exceed the maximum horizon")

    symbols = tuple(args.symbols) if args.symbols else SYMBOLS
    results = []
    failures = []
    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(_audit_symbol, symbol, args.sample_bars): symbol for symbol in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                failures.append((symbol, type(exc).__name__, str(exc)))

    print("=== HIDDEN_DEMAND REAL WEIGHT SAFETY AUDIT ===")
    print(f"symbols requested: {len(symbols)}")
    print(f"symbols scanned: {len(symbols) - len(failures)}")
    print(f"promoted contexts: {sorted(PROMOTED_CONTEXTS)}")
    print()
    print(f"{'Weight':>8}{'Events':>10}{'Mean dStrength':>17}{'Mean dConfidence':>19}")
    for weight in WEIGHTS:
        changes_s = [x for result in results for x in result["totals"][weight]["strength_change"]]
        changes_c = [x for result in results for x in result["totals"][weight]["confidence_change"]]
        mean_s = sum(changes_s) / len(changes_s) if changes_s else 0.0
        mean_c = sum(changes_c) / len(changes_c) if changes_c else 0.0
        print(f"{weight:>8.2f}{len(changes_s):>10}{mean_s:>16.4f}{mean_c:>18.4f}")

    print()
    print("INTERPRETATION")
    print("Scores above are generated from the live ProfessionalScoringEngine formulas with a synthetic HIDDEN_DEMAND contribution; config.py and production collectors are untouched.")
    if failures:
        print()
        print("=== SCAN FAILURES ===")
        for symbol, error_type, message in failures:
            print(f"{symbol:<16}{error_type}: {message}")


if __name__ == "__main__":
    main()
