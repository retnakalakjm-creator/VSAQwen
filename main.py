"""
Professional VSA Swing Scanner

Main Entry Point
"""

from __future__ import annotations

import argparse

from data import completed_weekly_only, daily_to_weekly, download_data
from metrics_engine import MetricsEngine
from production_scanner import scan_actionable_production
from scanner import ScannerEngine


def main() -> None:
    """Run the production VSA scanner and print actionable candidates."""
    parser = argparse.ArgumentParser(description="Professional VSA Swing Scanner")
    parser.add_argument("symbol", nargs="?", default="SRF.NS")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument(
        "--full-replay",
        action="store_true",
        help="Use the original full replay scanner instead of the incremental production path.",
    )
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
    weekly = completed_weekly_only(daily_to_weekly(daily))
    print(f"Weekly bars : {len(weekly)}")
    print("\nRunning Metrics Engine...")
    metrics = MetricsEngine().calculate(weekly)
    print("✓ Metrics completed")
    print("\nRunning actionable scanner...")
    if args.full_replay:
        candidates = ScannerEngine().scan_actionable(metrics)
        scanner_mode = "full replay"
    else:
        candidates = scan_actionable_production(metrics, symbol=symbol)
        scanner_mode = "incremental"
    print(
        f"✓ Scanner completed ({scanner_mode}): "
        f"{len(candidates)} actionable candidates"
    )
    print("\nACTIONABLE CANDIDATES")
    print("=" * 60)
    for rank, candidate in enumerate(candidates[: args.limit], start=1):
        print(rank, {
            "symbol": symbol,
            "bar_index": candidate.bar_index,
            "week": candidate.week,
            "signal_bar_index": candidate.signal_bar_index,
            "signal_week": candidate.signal_week,
            "execution_bar_index": candidate.execution_bar_index,
            "execution_week": candidate.execution_week,
            "execution_available": candidate.execution_available,
            "execution_pending": candidate.execution_pending,
            "execution_note": candidate.execution_note,
            "qualification": candidate.qualification,
            "actionable": candidate.actionable,
            "base_score": candidate.base_score,
            "ranking_score": candidate.ranking_score,
            "net_strength": candidate.net_strength,
            "net_pressure": candidate.net_pressure,
            "confidence": candidate.confidence,
            "target_bar_evidence_codes": candidate.target_bar_evidence_codes,
            "campaign_evidence_codes": candidate.campaign_evidence_codes,
            "qualifying_evidence_codes": candidate.qualifying_evidence_codes,
            "scoring_evidence_codes": candidate.scoring_evidence_codes,
            "scoring_bar_index": candidate.scoring_bar_index,
        })


if __name__ == "__main__":
    main()
