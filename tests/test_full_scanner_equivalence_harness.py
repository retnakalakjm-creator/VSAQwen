from __future__ import annotations

import pandas as pd
import pytest

from scanner import ScannerEngine
from tests.full_scanner_equivalence_harness import run_production_path_equivalence


def _metrics() -> pd.DataFrame:
    count = 80
    weeks = [f"W{i:03d}" for i in range(count)]
    base = [100.0 + (i % 9) for i in range(count)]
    return pd.DataFrame(
        {
            "High": [value + 2.0 for value in base],
            "Low": [value - 2.0 for value in base],
            "Open": base,
            "Close": base,
            "Volume": [1000.0 + i for i in range(count)],
            "week_beginning": weeks,
            "Average Spread": [4.0] * count,
        }
    )


def test_target_index_validation() -> None:
    metrics = _metrics()
    with pytest.raises(ValueError, match="target_index"):
        run_production_path_equivalence(
            metrics,
            target_index=ScannerEngine.MIN_REPLAY_BARS - 1,
        )


def test_target_index_must_leave_valid_cutoff() -> None:
    metrics = _metrics()
    with pytest.raises(IndexError, match="outside metrics"):
        run_production_path_equivalence(
            metrics,
            target_index=len(metrics),
        )
