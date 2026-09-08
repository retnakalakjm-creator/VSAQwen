from __future__ import annotations

import inspect

from incremental_scanner import IncrementalScannerEngine


FORBIDDEN_PRIVATE_TREND_ACCESS = (
    "._reset",
    "._swing_engine",
    "._classified_swings",
    "._structural_swings",
    "._classify_swings",
    "._create_structure",
    "._build_result",
)


def test_incremental_scanner_does_not_use_trend_analyzer_private_internals() -> None:
    source = inspect.getsource(IncrementalScannerEngine)

    for private_access in FORBIDDEN_PRIVATE_TREND_ACCESS:
        assert private_access not in source


def test_incremental_scanner_does_not_call_scanner_private_anomaly_helper() -> None:
    source = inspect.getsource(IncrementalScannerEngine.resume_latest)

    assert "self._scanner._signal_bar_anomaly" not in source
