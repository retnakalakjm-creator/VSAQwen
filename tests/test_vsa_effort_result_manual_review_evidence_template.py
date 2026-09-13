import csv
import json
from io import StringIO

import pytest

from audit.export_effort_result_manual_review_evidence_template import (
    PRODUCTION_BOUNDARY,
    REVIEW_COLUMNS,
    REVIEW_STATUS_PENDING,
    build_manual_review_evidence_template,
    render_manual_review_template_csv,
    render_manual_review_template_markdown,
)


def _proposal_report():
    return {
        "report_type": "effort_result_calibration_design_proposal",
        "source": "historical_effort_result_validation.csv",
        "rows": 7470,
        "targets": ["RESULT_GT_EFFORT", "EFFORT_RESULT+SUPPLY_COMING_IN"],
        "target_proposals": [
            {
                "target": "RESULT_GT_EFFORT",
                "proposal_status": "ready_for_calibration_design_review",
                "candidate_direction": "mixed",
                "proposed_signal_role": "direction_sensitive_calibration_candidate",
                "matched_bars": 88,
                "exported_examples": 20,
            },
            {
                "target": "EFFORT_RESULT+SUPPLY_COMING_IN",
                "proposal_status": "ready_for_calibration_design_review",
                "candidate_direction": "negative",
                "proposed_signal_role": "bearish_calibration_candidate",
                "matched_bars": 61,
                "exported_examples": 20,
            },
        ],
    }


def _casebook_report():
    return {
        "casebooks": [
            {
                "target": "RESULT_GT_EFFORT",
                "examples": [
                    {
                        "symbol": "HDFCBANK.NS",
                        "week_beginning": "2024-03-18",
                        "forward_return_1": -0.01,
                        "forward_return_2": -0.02,
                        "forward_return_4": 0.01,
                    },
                    {
                        "symbol": "COALINDIA.NS",
                        "week_beginning": "2023-05-01",
                        "forward_return_1": 0.03,
                        "forward_return_2": 0.02,
                        "forward_return_4": -0.01,
                    },
                ],
            },
            {
                "target": "EFFORT_RESULT+SUPPLY_COMING_IN",
                "examples": [
                    {
                        "symbol": "GODREJPROP.NS",
                        "week_beginning": "2024-09-23",
                        "forward_return_1": -0.04,
                        "forward_return_2": -0.05,
                        "forward_return_4": -0.02,
                    }
                ],
            },
        ]
    }


def test_builds_template_rows_from_casebook_examples():
    report = build_manual_review_evidence_template(
        _proposal_report(), casebook_report=_casebook_report(), max_examples_per_target=2
    )

    assert report["report_type"] == "effort_result_manual_review_evidence_template"
    assert report["template_row_count"] == 3
    assert report["target_count"] == 2
    assert report["next_stage"] == "manual_visual_review"

    first = report["review_rows"][0]
    assert first["target"] == "RESULT_GT_EFFORT"
    assert first["example_rank"] == 1
    assert first["symbol"] == "HDFCBANK.NS"
    assert first["week_beginning"] == "2024-03-18"
    assert first["manual_review_status"] == REVIEW_STATUS_PENDING
    assert first["approved_for_calibration_design"] == "false"


def test_generates_placeholder_row_when_casebook_examples_missing():
    report = build_manual_review_evidence_template(_proposal_report(), max_examples_per_target=20)

    assert report["template_row_count"] == 2
    assert {row["symbol"] for row in report["review_rows"]} == {""}
    assert all(row["manual_review_status"] == REVIEW_STATUS_PENDING for row in report["review_rows"])


def test_limits_examples_per_target_and_preserves_target_summary_counts():
    report = build_manual_review_evidence_template(
        _proposal_report(), casebook_report=_casebook_report(), max_examples_per_target=1
    )

    assert report["template_row_count"] == 2
    summaries = {row["target"]: row for row in report["target_summaries"]}
    assert summaries["RESULT_GT_EFFORT"]["template_rows"] == 1
    assert summaries["RESULT_GT_EFFORT"]["casebook_examples_available"] == 1
    assert summaries["EFFORT_RESULT+SUPPLY_COMING_IN"]["template_rows"] == 1


def test_production_boundary_remains_closed_globally_and_per_target():
    report = build_manual_review_evidence_template(
        _proposal_report(), casebook_report=_casebook_report()
    )

    for key, expected in PRODUCTION_BOUNDARY.items():
        assert report[key] is expected
    assert report["automatic_promotion_allowed"] is False

    for summary in report["target_summaries"]:
        assert summary["audit_only"] is True
        assert summary["template_only"] is True
        assert summary["production_change_allowed"] is False
        assert summary["may_change_scoring"] is False
        assert summary["may_activate_detector"] is False


def test_csv_render_uses_stable_review_columns():
    report = build_manual_review_evidence_template(
        _proposal_report(), casebook_report=_casebook_report(), max_examples_per_target=1
    )
    rendered = render_manual_review_template_csv(report)
    rows = list(csv.DictReader(StringIO(rendered)))

    assert rows
    assert list(rows[0].keys()) == list(REVIEW_COLUMNS)
    assert rows[0]["target"] == "RESULT_GT_EFFORT"
    assert rows[0]["manual_review_status"] == REVIEW_STATUS_PENDING
    assert rows[0]["reviewer"] == ""
    assert rows[0]["approved_for_calibration_design"] == "false"


def test_markdown_render_includes_instructions_and_options():
    report = build_manual_review_evidence_template(
        _proposal_report(), casebook_report=_casebook_report(), max_examples_per_target=1
    )
    rendered = render_manual_review_template_markdown(report)

    assert "Effort/Result Manual Review Evidence Template" in rendered
    assert "Reviewer Instructions" in rendered
    assert "Production change allowed: false" in rendered
    assert "RESULT_GT_EFFORT" in rendered
    assert "pending_manual_review" in rendered


def test_rejects_non_positive_example_limit():
    with pytest.raises(ValueError, match="max_examples_per_target must be positive"):
        build_manual_review_evidence_template(_proposal_report(), max_examples_per_target=0)
