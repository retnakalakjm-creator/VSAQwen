from __future__ import annotations

import argparse
import re
from pathlib import Path

from background.qualification import PatternQualification, PatternQualificationEngine
from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from trend import TrendAnalyzer


DEFAULT_SYMBOL_SOURCE = Path("Diagnose output.txt")
MIN_REPLAY_BARS = 20
STRUCTURAL_CODES = frozenset({
    "structural_progression_improving",
    "structural_progression_weakening",
})


def _symbols_from_diagnose_output(path: Path) -> list[str]:
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8", errors="ignore")
    symbols = re.findall(r"['\"]symbol['\"]\s*:\s*['\"]([^'\"]+)['\"]", text)
    return list(dict.fromkeys(symbols))


def _structural_items(result):
    return tuple(
        item
        for item in result.evidence
        if str(item.code) in STRUCTURAL_CODES
    )


def _qualification_name(qualification):
    return str(qualification.qualification)


def scan_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    engine = PatternQualificationEngine()
    evidence_engine = EvidenceEngine()

    history = []
    seen_events: set[tuple[int, str]] = set()
    previous = PatternQualification.UNQUALIFIED
    previous_bars: tuple[int, ...] = ()
    candidates: list[dict] = []

    for target_index in range(MIN_REPLAY_BARS, len(metrics)):
        replay_metrics = metrics.iloc[: target_index + 1].copy()
        trend = TrendAnalyzer().analyze(replay_metrics)
        structural_swings = list(trend.structure.structural_swings)

        result = evidence_engine.collect(
            metrics=replay_metrics,
            trend=trend,
            structural_swings=structural_swings,
        )
        structural_items = _structural_items(result)

        if not structural_items:
            continue

        history.append(result)
        qualification = engine.evaluate(history)
        current = qualification.qualification

        new_events = [
            item
            for item in structural_items
            if (item.bar_index, str(item.code)) not in seen_events
        ]

        for item in new_events:
            seen_events.add((item.bar_index, str(item.code)))

            opposing = (
                previous == PatternQualification.PERSISTENT_BULLISH
                and str(item.code) == "structural_progression_weakening"
            ) or (
                previous == PatternQualification.PERSISTENT_BEARISH
                and str(item.code) == "structural_progression_improving"
            )

            if not opposing:
                continue

            if current not in (
                PatternQualification.UNQUALIFIED,
                PatternQualification.PERSISTENT_BULLISH,
                PatternQualification.PERSISTENT_BEARISH,
            ):
                continue

            candidates.append({
                "symbol": symbol,
                "event_bar_index": item.bar_index,
                "week": item.week_beginning,
                "opposing_event": str(item.code),
                "previous_qualification": str(previous),
                "new_qualification": str(current),
                "qualification_before_bars": list(previous_bars),
                "qualification_after_bars": list(
                    qualification.evidence_bar_indices
                ),
                "transition": f"{previous} -> {current}",
                "invalidation": current == PatternQualification.UNQUALIFIED,
            })

        previous = current
        previous_bars = tuple(qualification.evidence_bar_indices)

    return candidates


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Find structural qualification invalidation/flip candidates "
            "across all symbols listed in Diagnose output.txt."
        )
    )
    parser.add_argument(
        "symbols",
        nargs="*",
        help="Optional Yahoo symbols. If omitted, symbols are read from Diagnose output.txt.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SYMBOL_SOURCE,
        help="Diagnostic text file used to discover symbols.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    symbols = args.symbols or _symbols_from_diagnose_output(args.source)

    if not symbols:
        raise RuntimeError(
            "No symbols found. Pass symbols explicitly, e.g. "
            "python diagnose_structural_invalidation.py DLF.NS BHARTIARTL.NS"
        )

    print("=" * 78)
    print("STRUCTURAL INVALIDATION CANDIDATE SEARCH")
    print("=" * 78)
    print({"symbols": symbols, "count": len(symbols)})

    all_candidates: list[dict] = []

    for symbol in symbols:
        print()
        print(f"SCANNING {symbol}")
        try:
            candidates = scan_symbol(symbol)
        except Exception as exc:
            print({"symbol": symbol, "status": "ERROR", "error": str(exc)})
            continue

        all_candidates.extend(candidates)

        if not candidates:
            print({"symbol": symbol, "candidates": 0})
            continue

        for candidate in candidates:
            print("CANDIDATE")
            print(candidate)
            print({
                "test_bars": [
                    max(0, candidate["event_bar_index"] - 1),
                    candidate["event_bar_index"],
                    candidate["event_bar_index"] + 1,
                ],
            })

    print()
    print("=" * 78)
    print("ALL CANDIDATES")
    print("=" * 78)

    if not all_candidates:
        print("No opposing structural invalidation/flip candidates found.")
        return

    for index, candidate in enumerate(all_candidates, start=1):
        print(index, candidate)

    print()
    print({
        "candidate_count": len(all_candidates),
        "invalidation_count": sum(
            bool(item["invalidation"]) for item in all_candidates
        ),
    })


if __name__ == "__main__":
    main()
