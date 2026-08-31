from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from model.evidence_result_model import EvidenceResult
from model.score_model import ProfessionalScoreResult
from models import EvidenceCode
from professional.scoring_engine import ProfessionalScoringEngine
from scanner import ScannerCandidate, ScannerEngine
from trend import TrendAnalyzer

from run_nse_increasing_demand_universe_audit import SYMBOLS


def _has_increasing_demand(evidence: EvidenceResult) -> bool:
    return any(item.code == EvidenceCode.INCREASING_DEMAND for item in evidence.evidence)


def _legacy_candidate(candidate: ScannerCandidate) -> ScannerCandidate:
    scores = candidate.professional.scores
    legacy_confidence = ProfessionalScoringEngine._measure_confidence(scores)
    legacy_scores = replace(scores, confidence=legacy_confidence)
    legacy_professional = ProfessionalScoreResult(
        scores=legacy_scores,
        evidence=candidate.professional.evidence,
    )
    return replace(candidate, professional=legacy_professional)


def _scan_symbol(symbol: str, sample_bars: int, refresh: bool) -> list[dict]:
    daily = download_data(symbol, refresh=refresh)
    weekly = daily_to_weekly(daily)
    metrics = __import__('metrics_engine').MetricsEngine().calculate(weekly)
    scanner = ScannerEngine()
    sample_start = max(scanner.MIN_REPLAY_BARS, len(metrics) - sample_bars)
    history = []
    rows = []

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        evidence = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=list(trend.structure.structural_swings),
        )
        history.append(evidence)
        if index < sample_start or not _has_increasing_demand(evidence):
            continue

        current = scanner.evaluate(
            trend=trend,
            evidence=evidence,
            history=history,
            bar_index=index,
            week=scanner._week_at(metrics, index),
        )
        legacy = _legacy_candidate(current)
        if legacy.actionable == current.actionable:
            continue

        rows.append({
            "symbol": symbol,
            "bar_index": index,
            "week": scanner._week_at(metrics, index),
            "direction": str(trend.structure.direction.value),
            "state": str(trend.structure.state.value),
            "qualification": str(legacy.qualification.value),
            "legacy_actionable": legacy.actionable,
            "gated_actionable": current.actionable,
            "legacy_confidence": legacy.confidence,
            "gated_confidence": current.confidence,
            "score": current.base_score,
            "pressure": current.net_pressure,
        })

    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Isolate the production increasing_demand gate impact.")
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    rows: list[dict] = []
    skipped = []
    for symbol in SYMBOLS:
        try:
            rows.extend(_scan_symbol(symbol, args.sample_bars, args.refresh))
        except Exception as exc:
            skipped.append((symbol, type(exc).__name__, str(exc)))

    print("=== INCREASING_DEMAND GATE IMPACT AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols with changed actionability: {len({r['symbol'] for r in rows})}")
    print(f"changed cases: {len(rows)}")
    print()
    print(f"{'State':<12}{'Direction':<10}{'Legacy->Gated':<16}{'Cases':>8}")

    groups: dict[tuple[str, str, str], list[dict]] = {}
    for row in rows:
        key = (row["state"], row["direction"], f"{row['legacy_actionable']}->{row['gated_actionable']}")
        groups.setdefault(key, []).append(row)
    for (state, direction, change), bucket in sorted(groups.items()):
        print(f"{state:<12}{direction:<10}{change:<16}{len(bucket):>8}")

    if rows:
        print()
        print("=== CASES ===")
        for row in rows:
            print(
                f"{row['symbol']:<14} bar={row['bar_index']:<4} "
                f"state={row['state']:<10} dir={row['direction']:<5} "
                f"action={row['legacy_actionable']}->{row['gated_actionable']} "
                f"confidence={row['legacy_confidence']:.4f}->{row['gated_confidence']:.4f} "
                f"score={row['score']:.4f} pressure={row['pressure']:.4f}"
            )

    if skipped:
        print()
        print("=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
