"""Adapter between the GUI and the production scanner pipeline."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from data import daily_to_weekly, download_data
from metrics_engine import MetricsEngine
from scanner import ScannerCandidate, ScannerEngine

MAX_WORKERS = 4


@dataclass(slots=True, frozen=True)
class ScanItem:
    symbol: str
    candidate: ScannerCandidate | None = None
    error: str | None = None


class MarketScanService:
    """Runs the existing production scanner without putting logic in GUI widgets."""

    def scan_symbol(self, symbol: str) -> ScanItem:
        try:
            # Live scans use the data-layer cache and incremental refresh path.
            # Never force a full historical download here.
            daily = download_data(symbol, refresh=False)
            weekly = daily_to_weekly(daily)
            metrics = MetricsEngine().calculate(weekly)
            candidate = ScannerEngine().scan_to_index(metrics, len(metrics) - 1)
            return ScanItem(symbol=symbol, candidate=candidate)
        except Exception as exc:
            return ScanItem(symbol=symbol, error=str(exc))

    def scan(self, symbols: list[str]) -> list[ScanItem]:
        """Scan symbols concurrently while keeping scanner state isolated per stock."""
        if not symbols:
            return []

        with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(symbols))) as executor:
            return list(executor.map(self.scan_symbol, symbols))
