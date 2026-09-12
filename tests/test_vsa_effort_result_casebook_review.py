from __future__ import annotations

import json

from audit.review_effort_result_casebook import (
    STATUS_NEEDS_ATTENTION,
    STATUS_NEEDS_EXAMPLES,
    STATUS_NEEDS_FORWARD_OUTCOMES,
    STATUS_READY,
    build_casebook_review_report,
    render_casebook_review_markdown,
)


def _example(
    *,
    symbol: str,
    week: str,
    r1: float | None = None,
    r2: float | None = None,
    r4: float | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {
        "symbol": symbol,
        "week_beginning": week,
        "bar_index": 10,
        "close": 100.0,
        "volume_ratio": 0.5,
        "spread_ratio": 1.6,
    }
    if r1 is not None:
        row["forward_return_1"] = r1
    if r2 is not None:
        row["forward_return_2"] = r2
    if r4 is not None:
        row["forward_return_4"] = r4
    return row


def _casebook_report() -> dict[str, object]:
    return {
        "report_type": "effort_result_casebook",
        "source": "historical_effort_result_validation.csv",
        "rows": 7470,
        "targets": ["RESULT_GT_EFFORT", "EFFORT_RESULT+SUPPLY_COMING_IN"],
        "horizons": [1, 2, 4],
        "casebooks": [
            {
                "target": "RESULT_GT_EFFORT",
                "matched_bars": 88,
                "exported_examples": 2,
                "examples": [
                    _example(symbol="LT.NS", week="2026-03-02", r1=-0.02, r2=-0.04, r4=-0.01),
                    _example(symbol="RELIANCE.NS", week="2026-03-09", r1=0.03, r2=-0.01, r4=-0.02),
                ],
            },
            {
                "target": "EFFORT_RESULT+SUPPLY_COMING_IN",
                "matched_bars": 61,
                "exported_examples": 1,
                "examples": [
                    _example(symbol="LT.NS", week="2026-04-06", r1=-0.03, r2=-0.02, r4=-0.05),
                ],
            },
        ],
        "audit_only": True,
    }


def test_casebook_review_summarizes_ready_targets_and_forward_outcomes() -> None:
    report = build_casebook_review_report(_casebook_report())

    reviews = {row["target"]: row for row in report["target_reviews"]}
    result_gt_effort = reviews["RESULT_GT_EFFORT"]

    assert report["report_type"] == "effort_result_casebook_review"
    assert report["report_schema_version"] == 1
    assert report["review_status"] == STATUS_READY
    assert report["ready_target_count"] == 2
    assert report["blocked_target_count"] == 0
    assert report["total_matched_bars"] == 149
    assert result_gt_effort["review_status"] == STATUS_READY
    assert result_gt_effort["symbols"] == ["LT.NS", "RELIANCE.NS"]
    assert result_gt_effort["first_week"] == "2026-03-02"
    assert result_gt_effort["last_week"] == "2026-03-09"
    horizon_1 = result_gt_effort["horizon_summaries"][0]
    assert horizon_1["horizon"] == 1
    assert horizon_1["examples_with_forward_return"] == 2
    assert horizon_1["positive_count"] == 1
    assert horizon_1["negative_count"] == 1


def test_casebook_review_blocks_targets_without_examples_or_forward_outcomes() -> None:
    raw = _casebook_report()
    raw["casebooks"] = [
        {
            "target": "RESULT_GT_EFFORT",
            "matched_bars": 0,
            "exported_examples": 0,
            "examples": [],
        },
        {
            "target": "EFFORT_RESULT+SUPPLY_COMING_IN",
            "matched_bars": 2,
            "exported_examples": 1,
            "examples": [_example(symbol="LT.NS", week="2026-04-06")],
        },
    ]

    report = build_casebook_review_report(raw)
    reviews = {row["target"]: row for row in report["target_reviews"]}

    assert report["review_status"] == STATUS_NEEDS_ATTENTION
    assert report["ready_target_count"] == 0
    assert report["blocked_target_count"] == 2
    assert reviews["RESULT_GT_EFFORT"]["review_status"] == STATUS_NEEDS_EXAMPLES
    assert reviews["EFFORT_RESULT+SUPPLY_COMING_IN"]["review_status"] == STATUS_NEEDS_FORWARD_OUTCOMES


def test_casebook_review_keeps_production_boundary_closed() -> None:
    report = build_casebook_review_report(_casebook_report())

    assert report["audit_only"] is True
    assert report["may_change_scoring"] is False
    assert report["may_change_ranking"] is False
    assert report["may_change_actionability"] is False
    assert report["may_activate_detector"] is False
    assert report["requires_manual_case_review"] is True
    assert report["requires_separate_production_pr"] is True
    assert all(row["may_change_scoring"] is False for row in report["target_reviews"])
    assert all(row["requires_separate_production_pr"] is True for row in report["target_reviews"])


def test_casebook_review_renders_markdown_and_json() -> None:
    report = build_casebook_review_report(_casebook_report())
    markdown = render_casebook_review_markdown(report)

    assert "# Effort/Result Casebook Review" in markdown
    assert "RESULT_GT_EFFORT" in markdown
    assert "EFFORT_RESULT+SUPPLY_COMING_IN" in markdown
    assert "May change scoring: false" in markdown
    assert "1w:" in markdown
    json.dumps(report)
