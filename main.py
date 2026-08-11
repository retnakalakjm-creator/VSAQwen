"""
Professional VSA Swing Scanner

Main Entry Point
"""

from __future__ import annotations

import argparse

from data import daily_to_weekly, download_data
from metrics_engine import MetricsEngine
from scanner import ScannerEngine


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
    candidates = ScannerEngine().scan_actionable(metrics)

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


if __name__ == "__main__":
    main()
