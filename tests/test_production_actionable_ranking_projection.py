from __future__ import annotations

from test_production_score_finite_audit import _production_candidates
from scanner import rank_actionable_candidates, rank_candidates


def test_actionable_ranking_matches_filtered_full_production_ranking() -> None:
    candidates = _production_candidates()

    expected = [candidate for candidate in rank_candidates(candidates) if candidate.actionable]
    actual = rank_actionable_candidates(candidates)

    assert actual == expected


def test_actionable_ranking_is_idempotent_on_actionable_production_candidates() -> None:
    candidates = [candidate for candidate in _production_candidates() if candidate.actionable]

    ranked = rank_actionable_candidates(candidates)
    reranked = rank_actionable_candidates(ranked)

    assert reranked == ranked
