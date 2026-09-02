from __future__ import annotations

import numpy as np

from benchmark_history_snapshots import make_inputs
from market_structure.batched_structural_scorer import score_prepared_batch
from market_structure.professional_scorer import ProfessionalScorer


def test_batched_structural_scores_match_scalar_scores() -> None:
    metrics, swings = make_inputs(500)
    scorer = ProfessionalScorer()
    arrays = scorer._metric_arrays(metrics)
    indices = tuple(swing.metrics_index for swing in swings)
    snapshots = scorer.prepare_history_snapshots(
        swings,
        arrays,
        10,
    )

    actual = score_prepared_batch(
        scorer._structure,
        snapshots,
        arrays[4],
        arrays[5],
        indices,
    )

    for index, snapshot in enumerate(snapshots):
        if snapshot is None:
            assert all(values[index] == 0.0 for values in actual)
            continue

        expected = scorer._structure._prepared_values(
            snapshot=snapshot,
            volume=float(arrays[4][indices[index]]),
            spread=float(arrays[5][indices[index]]),
        )

        for value, expected_value in zip(
            (values[index] for values in actual),
            expected,
        ):
            assert np.isclose(value, expected_value)
