from __future__ import annotations

import json

import pytest

from audit.propose_effort_result_calibration_design import (
    PROPOSAL_BLOCKED_STATUS,
    PROPOSAL_READY_STATUS,
    build_calibration_design_proposal,
    render_calibration_design_markdown,
)


def _target_review(
    target: str,
    *,
    exported_examples: int = 20,
    review_status: str = "ready_for_manual_visual_review",
    means: tuple[float, ...] = (-0.01, -0.02, -0.03),
) -> dict[str, object]:
    return {
        "target": target,
        "review_status": review_status,
        "matched_bars": exported_examples + 10,
        "exported_examples": exported_examples,
        "symbols": ["LT.NS", "HDFCBANK.NS"],
        "first_week": "2024-01-01",
        "last_week": "2024-03-01",
        "horizon_summaries": [
            {
                "horizon": horizon,
                "examples_with_forward_return": exported_examples,
                "mean_forward_return": mean,
                "positive_count": 3,
                "negative_count": 7,
                "flat_count": 0,
            }
            for horizon, mean in zip((1, 2, 4), means)
        ],
    }


def _review_report() -> dict[str, object]:
    return {
        "report_type": "effort_result_casebook_review",
        "source": "historical_effort_result_validation.csv",
        "rows": 7470,
        "targets": ["RESULT_GT_EFFORT", "EFFORT_RESULT+SUPPLY_COMING_IN"],
        "horizons": [1, 2, 4],
        "target_reviews": [
            _target_review("RESULT_GT_EFFORT"),
            _target_review("EFFORT_RESULT+SUPPLY_COMING_IN"),
        ],
    }


def test_calibration_design_proposal_keeps_production_boundary() -> None:
    proposal = build_calibration_design_proposal(_review_report())

    assert proposal["report_type"] == "effort_result_calibration_design_proposal"
    assert proposal["report_schema_version"] == 1
    assert proposal["proposal_status"] == PROPOSAL_READY_STATUS
    assert proposal["ready_proposal_count"] == 2
    assert proposal["blocked_proposal_count"] == 0
    assert proposal["audit_only"] is True
    assert proposal["proposal_only"] is True
    assert proposal["production_change_allowed"] is False
    assert proposal["may_change_scoring"] is False
    assert proposal["may_change_ranking"] is False
    assert proposal["may_change_actionability"] is False
    assert proposal["may_activate_detector"] is False
    assert proposal["requires_manual_case_review"] is True
    assert proposal["requires_separate_production_pr"] is True


def test_target_proposal_infers_direction_and_work_items() -> None:
    proposal = build_calibration_design_proposal(_review_report())
    target = proposal["target_proposals"][0]

    assert target["proposal_status"] == PROPOSAL_READY_STATUS
    assert target["candidate_direction"] == "negative"
    assert target["proposed_signal_role"] == "bearish_calibration_candidate"
    assert target["readiness_checks"] == {
        "casebook_ready": True,
        "has_minimum_examples": True,
        "has_forward_outcomes": True,
        "direction_review_available": True,
    }
    assert any(
        "separate production PR" in step
        for step in target["proposed_calibration_work"]
    )


def test_proposal_blocks_when_review_inputs_are_incomplete() -> None:
    review = _review_report()
    review["target_reviews"] = [
        _target_review("RESULT_GT_EFFORT", exported_examples=2),
        _target_review(
            "EFFORT_RESULT+SUPPLY_COMING_IN",
            review_status="needs_forward_outcomes",
        ),
    ]

    proposal = build_calibration_design_proposal(review, min_examples_per_target=5)

    assert proposal["proposal_status"] == "needs_attention"
    assert proposal["ready_proposal_count"] == 0
    assert proposal["blocked_proposal_count"] == 2
    assert all(
        row["proposal_status"] == PROPOSAL_BLOCKED_STATUS
        for row in proposal["target_proposals"]
    )


def test_markdown_and_json_are_reviewable_and_serializable() -> None:
    proposal = build_calibration_design_proposal(_review_report())
    markdown = render_calibration_design_markdown(proposal)

    assert "# Effort/Result Calibration Design Proposal" in markdown
    assert "Production change allowed: false" in markdown
    assert "RESULT_GT_EFFORT" in markdown
    assert "EFFORT_RESULT+SUPPLY_COMING_IN" in markdown
    assert "manual-review inputs are sufficient" in markdown
    json.dumps(proposal, sort_keys=True)


def test_proposal_validates_min_examples() -> None:
    with pytest.raises(ValueError, match="min_examples_per_target"):
        build_calibration_design_proposal(_review_report(), min_examples_per_target=0)
