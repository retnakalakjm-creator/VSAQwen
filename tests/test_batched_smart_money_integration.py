from __future__ import annotations

from market_structure.batched_smart_money import BatchedSmartMoneyAnalyzer
from market_structure.professional_scorer import ProfessionalScorer
from market_structure.structure_filter import StructureFilter
from models import SmartMoneyScore, Swing, SwingType
from test_professional_scorer import _metrics


def test_professional_scorer_returns_one_smart_money_score_per_index() -> None:
    scorer = ProfessionalScorer()
    metrics = _metrics()
    arrays = scorer._metric_arrays(metrics)
    indices = (0, 1, 2, 3)

    scores = scorer.smart_money_scores_batch(
        arrays,
        indices,
        include_components=True,
    )

    assert len(scores) == len(indices)
    assert all(isinstance(score, SmartMoneyScore) for score in scores)
    assert all(0.0 <= score.overall <= 1.0 for score in scores)


def test_batched_smart_money_path_does_not_call_scalar_scoring(monkeypatch) -> None:
    metrics = _metrics()
    scorer = ProfessionalScorer()
    arrays = scorer._metric_arrays(metrics)

    def fail_scalar(*args, **kwargs):
        raise AssertionError("scalar Smart Money scoring was called")

    monkeypatch.setattr(
        BatchedSmartMoneyAnalyzer,
        "score_values",
        fail_scalar,
    )

    scores = scorer.smart_money_scores_batch(
        arrays,
        (0, 1, 2, 3),
        include_components=True,
    )

    assert len(scores) == 4
    assert all(isinstance(score, SmartMoneyScore) for score in scores)


def test_structure_filter_does_not_build_all_smart_money_objects(monkeypatch) -> None:
    metrics = _metrics()
    swings = (
        Swing(
            type=SwingType.HIGH,
            price=12.0,
            bar_index=0,
            confirmation_index=1,
            week_beginning="2025-01-01",
            metrics_index=1,
        ),
        Swing(
            type=SwingType.LOW,
            price=18.0,
            bar_index=1,
            confirmation_index=2,
            week_beginning="2025-01-02",
            metrics_index=2,
        ),
    )

    def fail_batch_objects(*args, **kwargs):
        raise AssertionError("all Smart Money score objects were constructed")

    monkeypatch.setattr(
        BatchedSmartMoneyAnalyzer,
        "score_values_batch",
        fail_batch_objects,
    )
    monkeypatch.setattr(StructureFilter, "_is_structural", lambda self, score: False)

    result = StructureFilter().filter(swings, metrics)

    assert result == []
