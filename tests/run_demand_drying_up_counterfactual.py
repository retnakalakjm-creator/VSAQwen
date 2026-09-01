from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from background.qualification import PatternQualification
from data import daily_to_weekly, download_data
from evidence.demand_drying_up import collect_demand_drying_up
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from models import EvidenceCode
from scanner import ScannerEngine
from tests.conditional_demand_drying_up_counterfactual import apply_counterfactual
from tests.decision_outcome_labeling import label_outcome
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS
from trend import TrendAnalyzer


def _direction(candidate) -> int | None:
    qualification = candidate.qualification
    if qualification is PatternQualification.PERSISTENT_BULLISH:
        return 1
    if qualification is PatternQualification.PERSISTENT_BEARISH:
        return -1
    return None


def _has_demand_drying_up(candidate) -> bool:
    codes = {
        item.code
        for item in (
            *candidate.target_bar_evidence,
            *candidate.scoring_evidence,
            *candidate.campaign_evidence,
        )
    }
    return EvidenceCode.DEMAND_DRYING_UP in codes


def _has_ddu_current_bar(metrics, index: int, evidence_engine: EvidenceEngine) -> bool:
    current = evidence_engine._create_bar_context(metrics.iloc[index], index)
    previous = evidence_engine._create_bar_context(metrics.iloc[index - 1], index - 1)
    context = SimpleNamespace(current=current, previous=previous)
    return bool(collect_demand_drying_up(context))


def _audit_symbol(
    symbol: str,
    sample_bars: int,
    horizons: tuple[int, ...],
    refresh: bool,
) -> tuple[list[dict[str, object]], dict[str, int], Counter[str]]:
    daily = download_data(symbol, refresh=refresh)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    scanner = ScannerEngine()
    evidence_engine = EvidenceEngine()

    sample_start = max(
        scanner.MIN_REPLAY_BARS,
        len(metrics) - sample_bars - max(horizons),
    )
    sample_end = len(metrics) - max(horizons)

    rows: list[dict[str, object]] = []
    history = []
    counts = {
        "ddu_detected": 0,
        "candidate_evaluated": 0,
        "candidate_has_ddu": 0,
        "qualified": 0,
        "actionable_ddu": 0,
        "target_context_ddu": 0,
        "suppressed": 0,
    }
    reasons: Counter[str] = Counter()

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        evidence = evidence_engine.collect(
            metrics=replay,
            trend=trend,
            structural_swings=list(trend.structure.structural_swings),
        )
        history.append(evidence)

        if index < sample_start or index >= sample_end:
            continue
        if not _has_ddu_current_bar(metrics, index, evidence_engine):
            continue

        counts["ddu_detected"] += 1
        candidate = scanner.evaluate(
            trend=trend,
            evidence=evidence,
            history=history,
            bar_index=index,
            week=scanner._week_at(metrics, index),
        )
        counts["candidate_evaluated"] += 1

        if not _has_demand_drying_up(candidate):
            reasons["DDU missing from candidate evidence"] += 1
            continue
        counts["candidate_has_ddu"] += 1

        if candidate.qualification is PatternQualification.UNQUALIFIED:
            reasons[f"UNQUALIFIED: {candidate.reason}"] += 1
            continue
        counts["qualified"] += 1

        if not candidate.actionable:
            reasons[candidate.reason] += 1
            continue
        counts["actionable_ddu"] += 1

        counterfactual = apply_counterfactual(trend, candidate)
        if not counterfactual.suppressed:
            reasons["actionable but outside target context"] += 1
            continue
        counts["target_context_ddu"] += 1
        counts["suppressed"] += 1

        direction = _direction(candidate)
        if direction is None:
            reasons["suppressed but direction unavailable"] += 1
            continue

        for horizon in horizons:
            outcome = label_outcome(
                metrics,
                signal_index=index,
                direction=direction,
                horizon=horizon,
            )
            if outcome.forward_return is None:
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "state": counterfactual.state,
                    "direction": counterfactual.direction,
                    "horizon": horizon,
                    "forward_return": outcome.forward_return,
                    "mfe": outcome.maximum_favorable_excursion,
                    "mae": outcome.maximum_adverse_excursion,
                }
            )

    return rows, counts, reasons


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit-only counterfactual suppression for DEMAND_DRYING_UP target contexts."
    )
    parser.add_argument("--sample-bars", type=int, default=520)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    horizons = (3, 5, 10)

    all_rows: list[dict[str, object]] = []
    totals = {
        "ddu_detected": 0,
        "candidate_evaluated": 0,
        "candidate_has_ddu": 0,
        "qualified": 0,
        "actionable_ddu": 0,
        "target_context_ddu": 0,
        "suppressed": 0,
    }
    reasons: Counter[str] = Counter()
    skipped: list[tuple[str, str, str]] = []

    for symbol in SYMBOLS:
        try:
            rows, counts, symbol_reasons = _audit_symbol(
                symbol,
                args.sample_bars,
                horizons,
                args.refresh,
            )
            all_rows.extend(rows)
            reasons.update(symbol_reasons)
            for key, value in counts.items():
                totals[key] += value
        except Exception as exc:
            skipped.append((symbol, type(exc).__name__, str(exc)))

    print("=== DEMAND_DRYING_UP CONDITIONAL COUNTERFACTUAL AUDIT ===")
    print(f"symbols requested: {len(SYMBOLS)}")
    print(f"symbols with suppressed candidates: {len({row['symbol'] for row in all_rows})}")
    print(f"suppressed candidate-horizon rows: {len(all_rows)}")
    print()
    print(f"detected DDU candidate bars: {totals['ddu_detected']}")
    print(f"candidate bars evaluated: {totals['candidate_evaluated']}")
    print(f"candidate bars retaining DDU: {totals['candidate_has_ddu']}")
    print(f"qualified DDU candidate bars: {totals['qualified']}")
    print(f"actionable DDU candidate bars: {totals['actionable_ddu']}")
    print(f"target-context actionable DDU bars: {totals['target_context_ddu']}")
    print(f"suppressed candidate bars: {totals['suppressed']}")

    print()
    print("=== WHY DDU CANDIDATES DID NOT BECOME ACTIONABLE ===")
    for reason, count in reasons.most_common():
        print(f"{count:>6}  {reason}")

    print()
    print(
        f"{'State':<12}{'Direction':<10}{'H':>4}{'Cases':>8}"
        f"{'MeanRet':>12}{'Positive':>10}{'MeanMFE':>11}{'MeanMAE':>11}"
    )

    groups: dict[tuple[str, str, int], list[dict[str, object]]] = {}
    for row in all_rows:
        key = (
            str(row["state"]),
            str(row["direction"]),
            int(row["horizon"]),
        )
        groups.setdefault(key, []).append(row)

    for (state, direction, horizon), rows in sorted(groups.items()):
        returns = [float(row["forward_return"]) for row in rows]
        mfes = [float(row["mfe"]) for row in rows if row["mfe"] is not None]
        maes = [float(row["mae"]) for row in rows if row["mae"] is not None]
        print(
            f"{state:<12}{direction:<10}{horizon:>4}{len(returns):>8}"
            f"{sum(returns) / len(returns):>11.3%}"
            f"{sum(value > 0 for value in returns):>6}/{len(returns):<4}"
            f"{sum(mfes) / len(mfes):>10.3%}"
            f"{sum(maes) / len(maes):>10.3%}"
        )

    print()
    print("=== SUPPRESSED CASES BY SYMBOL ===")
    symbol_counts: dict[str, int] = {}
    for row in all_rows:
        symbol = str(row["symbol"])
        symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
    for symbol in SYMBOLS:
        if symbol in symbol_counts:
            print(f"{symbol:<14}{symbol_counts[symbol]:>6}")

    if skipped:
        print()
        print("=== SKIPPED ===")
        for symbol, error_type, message in skipped:
            print(f"{symbol:<14}{error_type}: {message}")


if __name__ == "__main__":
    main()
