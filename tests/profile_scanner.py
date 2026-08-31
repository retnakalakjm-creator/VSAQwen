from __future__ import annotations

import cProfile
import io
import pstats
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly
from metrics_engine import MetricsEngine
from scanner import ScannerEngine
from trend import TrendAnalyzer
from evidence.engine import EvidenceEngine


PROFILE_BARS = 260
TOP_ROWS = 30


def _weekly_bars(size: int = PROFILE_BARS):
    import numpy as np
    import pandas as pd

    index = np.arange(size, dtype=float)
    close = (
        100.0
        + np.sin(index / 4.0) * 5.0
        + index * 0.06
    )
    spread = 1.0 + (index % 8) * 0.14
    volume = 1000.0 + (index % 11) * 85.0 + index * 1.5
    return pd.DataFrame(
        {
            "week_beginning": [f"2025-W{i + 1:03d}" for i in range(size)],
            "open": close - 0.20,
            "high": close + spread / 2.0,
            "low": close - spread / 2.0,
            "close": close,
            "volume": volume,
        }
    )


def _profile(label: str, func) -> None:
    profiler = cProfile.Profile()
    profiler.enable()
    func()
    profiler.disable()

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.strip_dirs().sort_stats("cumulative").print_stats(TOP_ROWS)

    print(f"\n===== {label} =====")
    print(stream.getvalue())


def main() -> None:
    weekly = _weekly_bars()
    metrics = MetricsEngine().calculate(weekly)

    def trend_pass() -> None:
        TrendAnalyzer().analyze(metrics)

    def evidence_pass() -> None:
        trend = TrendAnalyzer().analyze(metrics)
        structural = list(trend.structure.structural_swings)
        EvidenceEngine().collect(
            metrics=metrics,
            trend=trend,
            structural_swings=structural,
        )

    def scanner_pass() -> None:
        ScannerEngine().scan_actionable(metrics)

    print(f"metrics bars: {len(metrics)}")
    _profile("TREND ONLY", trend_pass)
    _profile("TREND + EVIDENCE", evidence_pass)
    _profile("FULL scan_actionable", scanner_pass)


if __name__ == "__main__":
    main()
