"""
Professional VSA Swing Scanner

Main Entry Point
"""

from __future__ import annotations

import argparse

from data import daily_to_weekly, download_data
from metrics_engine import MetricsEngine
from scanner import ScannerCandidate, ScannerEngine


def _print_latest_diagnostic(symbol: str, candidate: ScannerCandidate) -> None:
    """Print the point-in-time decision trace already produced by the scanner."""

    def codes(items) -> tuple[str, ...]:
        return tuple(str(item.code) for item in items)

    print("\nLATEST BAR DIAGNOSTIC")
    print("=" * 60)
    print(
        {
            "symbol": symbol,
            "bar_index": candidate.bar_index,
            "week": candidate.week,
        }
    )

    print("\nQUALIFICATION")
    print(
        {
            "qualification": candidate.qualification,
            "actionable_evidence": candidate.qualification_result.is_actionable_evidence,
            "reason": candidate.reason,
            "evidence_codes": candidate.qualification_result.evidence_codes,
            "evidence_bar_indices": candidate.qualification_result.evidence_bar_indices,
        }
    )

    print("\nEVIDENCE")
    print(
        {
            "target_bar": codes(candidate.target_bar_evidence),
            "campaign": codes(candidate.campaign_evidence),
            "qualifying": codes(candidate.qualifying_evidence),
            "scoring": codes(candidate.scoring_evidence),
            "scoring_bar_index": candidate.scoring_bar_index,
            "scoring_evidence_age": candidate.scoring_evidence_age,
            "used_fallback_evidence": candidate.used_fallback_evidence,
        }
    )

    print("\nPROFESSIONAL SCORE")
    print(
        {
            "net_strength": candidate.net_strength,
            "net_pressure": candidate.net_pressure,
            "confidence": candidate.confidence,
        }
    )

    print("\nFINAL DECISION")
    print(
        {
            "actionable": candidate.actionable,
            "reason": candidate.reason,
        }
    )


def main() -> None:
    """Run the production VSA scanner and print actionable candidates."""

    parser = argparse.ArgumentParser(description="Professional VSA Swing Scanner")
    parser.add_argument("symbol", nargs="?", default="SRF.NS")
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()

    if args.limit <= 0:
        raise ValueError("limit must be greater than zero")

    symbol = args.symbol

    print("=" * 60)
    print("Professional VSA Swing Scanner")
    print("=" * 60)

    print(f"\nSymbol: {symbol}")

    print("\nDownloading data...")
    daily = download_data(symbol)
    print(f"Daily bars  : {len(daily)}")

    print("\nConverting to weekly data...")
    weekly = daily_to_weekly(daily)
    print(f"Weekly bars : {len(weekly)}")

    print("\nRunning Metrics Engine...")
    metrics = MetricsEngine().calculate(weekly)
    print("✓ Metrics completed")

    print("\nRunning actionable scanner...")
    scanner = ScannerEngine()
    candidates = scanner.scan_actionable(metrics)

    print(f"✓ Scanner completed: {len(candidates)} actionable candidates")
    print("\nACTIONABLE CANDIDATES")
    print("=" * 60)

    for rank, candidate in enumerate(candidates[: args.limit], start=1):
        print(
            rank,
            {
                "symbol": symbol,
                "bar_index": candidate.bar_index,
                "week": candidate.week,
                "qualification": candidate.qualification,
                "actionable": candidate.actionable,
                "base_score": candidate.base_score,
                "net_strength": candidate.net_strength,
                "net_pressure": candidate.net_pressure,
                "confidence": candidate.confidence,
                "target_bar_evidence_codes": candidate.target_bar_evidence_codes,
                "campaign_evidence_codes": candidate.campaign_evidence_codes,
                "qualifying_evidence_codes": candidate.qualifying_evidence_codes,
                "scoring_evidence_codes": candidate.scoring_evidence_codes,
                "scoring_bar_index": candidate.scoring_bar_index,
            },
        )

    if not candidates:
        latest_candidate = scanner.scan_to_index(metrics, len(metrics) - 1) if len(metrics) > scanner.MIN_REPLAY_BARS else None
        if latest_candidate is not None:
            _print_latest_diagnostic(symbol, latest_candidate)


if __name__ == "__main__":
    main()
