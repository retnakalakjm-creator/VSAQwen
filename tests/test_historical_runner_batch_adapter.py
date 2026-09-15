from __future__ import annotations

from collections.abc import Sequence

import pandas as pd

from historical_scanner import HistoricalScannerRunner


class RecordingBatchTransition:
    """Test double that records historical batch-adapter delegation."""

    def __init__(self) -> None:
        self.calls: list[tuple[pd.DataFrame, tuple[int, ...]]] = []

    def scan_to_indices(
        self,
        metrics: pd.DataFrame,
        target_indices: Sequence[int],
    ) -> dict[int, object]:
        targets = tuple(target_indices)
        self.calls.append((metrics, targets))
        return {target: object() for target in targets}


def test_historical_runner_scan_to_indices_delegates_to_transition_batch_boundary() -> None:
    metrics = pd.DataFrame({"close": [1.0, 2.0, 3.0, 4.0]})
    transition = RecordingBatchTransition()
    runner = HistoricalScannerRunner(transition=transition)  # type: ignore[arg-type]
    targets = (1, 3)

    candidates = runner.scan_to_indices(metrics, targets)

    assert list(candidates) == list(targets)
    assert len(transition.calls) == 1
    assert transition.calls[0][0] is metrics
    assert transition.calls[0][1] == targets
