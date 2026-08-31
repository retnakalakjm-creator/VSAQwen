from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from model.evidence_result_model import EvidenceResult
from model.score_model import ProfessionalScoreResult
from models import EvidenceCode
from professional.scoring_engine import ProfessionalScoringEngine
from scanner import ScannerEngine
from tests.decision_outcome_labeling import label_outcome
from trend import TrendAnalyzer
from run_nse_increasing_demand_universe_audit import SYMBOLS


def _has_id(evidence: EvidenceResult) -> bool:
    return any(item.code == EvidenceCode.INCREASING_DEMAND for item in evidence.evidence)


def _legacy_confidence(scores) -> float:
    return ProfessionalScoringEngine._measure_confidence(scores)


def _legacy_actionable(candidate) -> bool:
    scores = candidate.professional.scores
    legacy_scores = replace(scores, confidence=_legacy_confidence(scores))
    professional = ProfessionalScoreResult(scores=legacy_scores, evidence=candidate.professional.evidence)
    legacy = replace(candidate, professional=professional)
    return legacy.actionable


def main() -> None:
    parser = argparse.ArgumentParser(description="Outcome audit for cases blocked by the production increasing_demand gate.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    scanner = ScannerEngine()
    horizons = (3, 5, 10)
    rows: list[dict] = []
    skipped: list[tuple[str, str, str]] = []

    for symbol in SYMBOLS:
        try:
            daily = download_data(symbol, refresh=args.refresh)
            weekly = daily_to_weekly(daily)
            metrics = MetricsEngine().calculate(weekly)
            sample_start = max(scanner.MIN_REPLAY_BARS, len(metrics) - args.sample_bars)
            history = []

            for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
                replay = metrics.iloc[: index + 1].copy()
                trend = TrendAnalyzer().analyze(replay)
                evidence = EvidenceEngine().collect(
                    metrics=replay,
                    trend=trend,
                    structural_swings=list(trend.structure.structural_swings),
                )
                history.append(evidence)

                if index < sample_start or not _has_id(evidence):
                    continue

                gated = scanner.evaluate(
                    trend=trend,
                    evidence=evidence,
                    history=history,
                    bar_index=index,
                    week=scanner._week_at(metrics, index),
                )
                legacy_actionable = _legacy_actionable(gated)
                if not (legacy_actionable and not gated.actionable):
                    continue

                direction = 1 if trend.structure.direction.value == "up" else -1 if trend.structure.direction.value == "down" else 0
                if direction == 0:
                    continue

                for horizon in horizons:
                    if index + horizon >= len(metrics):
                        continue
                    outcome = label_outcome(metrics, signal_index=index, direction=direction, horizon=horizon)
                    rows.append({
                        "symbol": symbol,
                        "state": trend.structure.state.value,
                        "direction": trend.structure.direction.value,
                        "bar_index": index,
                        "horizon": horizon,
                        "return": outcome.forward_return,
                        "mfe": outcome.maximum_favorable_excursion,
                        "mae": outcome.maximum_adverse_excursion,
                        "positive": outcome.forward_return > 0,
                    })
        except Exception as exc:
            skipped.append((symbol, type(exc).__name__, str(exc)))

    print("=== INCREASING_DEMAND POST-GATE OUTCOME AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols with blocked cases: {len({r['symbol'] for r in rows})}")
    print(f"blocked case-horizon rows: {len(rows)}")
    print()
    print(f"{'State':<12}{'Direction':<10}{'Horizon':>8}{'Cases':>8}{'MeanRet':>12}{'WinRate':>10}{'MeanMFE':>12}{'MeanMAE':>12}")

    groups = defaultdict(list)
    for row in rows:
        groups[(row['state'], row['direction'], row['horizon'])].append(row)

    for key in sorted(groups):
        state, direction, horizon = key
        bucket = groups[key]
        n = len(bucket)
        mean_ret = sum(r['return'] for r in bucket) / n
        mean_mfe = sum(r['mfe'] for r in bucket) / n
        mean_mae = sum(r['mae'] for r in bucket) / n
        wins = sum(r['positive'] for r in bucket)
        print(f"{state:<12}{direction:<10}{horizon:>8}{n:>8}{mean_ret:>11.3%}{wins / n:>9.1%}{mean_mfe:>11.3%}{mean_mae:>11.3%}")

    if skipped:
        print()
        print("=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
