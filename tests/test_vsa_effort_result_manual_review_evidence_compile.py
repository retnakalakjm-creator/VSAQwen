from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

from audit.compile_effort_result_manual_review_evidence import (
    APPROVED_MANUAL_REVIEW_STATUS,
    REVIEW_STATUS_NEEDS_MORE,
    compile_manual_review_evidence,
    load_review_rows_csv,
    render_manual_review_evidence_markdown,
)


def _row(
    target: str = "RESULT_GT_EFFORT",
    *,
    rank: int = 1,
    approved: str = "true",
    status: str = APPROVED_MANUAL_REVIEW_STATUS,
    label: str = "true_positive",
    reviewer: str = "rk",
    review_date: str = "2026-09-13",
    symbol: str = "LT.NS",
    week: str = "2026-03-02",
) -> dict[str, str]:
    return {
        "target": target,
        "candidate_direction": "negative",
        "proposed_signal_role": "bearish_calibration_candidate",
        "source_proposal_status": "ready_for_calibration_design_review",
        "matched_bars": "61",
        "exported_examples": "20",
        "example_rank": str(rank),
        "symbol": symbol,
        "week_beginning": week,
        "forward_return_1": "-0.01",
        "forward_return_2": "-0.02",
        "forward_return_4": "-0.03",
        "reviewer": reviewer,
        "review_date": review_date,
        "manual_review_status": status,
        "visual_label": label,
        "true_false_positive_label": label,
        "structure_context": "supply present",
        "reviewer_notes": "confirmed visually",
        "approved_for_calibration_design": approved,
    }


def test_compiles_gate_ready_evidence_for_target_with_minimum_approved_rows() -> None:
    rows = [_row(rank=i, week=f"2026-03-{i:02d}") for i in range(1, 6)]

    report = compile_manual_review_evidence(rows, min_approved_examples_per_target=5)

    assert report["gate_evidence_ready"] is True
    assert report["approved_target_count"] == 1
    target = report["targets"][0]
    assert target["target"] == "RESULT_GT_EFFORT"
    assert target["manual_review_status"] == APPROVED_MANUAL_REVIEW_STATUS
    assert target["reviewed_examples"] == 5
    assert target["reviewer"] == "rk"
    assert target["reviewed_symbols"] == ["LT.NS"]
    assert len(target["reviewed_weeks"]) == 5
    assert target["automatic_promotion_allowed"] is False
    assert target["production_change_allowed"] is False


def test_target_needs_more_review_when_minimum_approved_rows_missing() -> None:
    rows = [_row(rank=1), _row(rank=2)]

    report = compile_manual_review_evidence(rows, min_approved_examples_per_target=5)

    assert report["gate_evidence_ready"] is False
    assert report["needs_review_target_count"] == 1
    target = report["targets"][0]
    assert target["manual_review_status"] == REVIEW_STATUS_NEEDS_MORE
    assert "has_minimum_approved_examples" in target["failed_evidence_checks"]


def test_false_positive_or_unapproved_rows_do_not_count_as_approved_evidence() -> None:
    rows = [
        _row(rank=1, label="false_positive"),
        _row(rank=2, approved="false"),
        _row(rank=3, status="needs_more_review", label="uncertain"),
        _row(rank=4),
    ]

    report = compile_manual_review_evidence(rows, min_approved_examples_per_target=2)

    target = report["targets"][0]
    assert target["reviewed_examples_total"] == 4
    assert target["approved_examples"] == 1
    assert target["false_positive_examples"] == 1
    assert target["uncertain_examples"] == 1
    assert target["manual_review_status"] == REVIEW_STATUS_NEEDS_MORE


def test_multiple_targets_are_compiled_separately() -> None:
    rows = [_row(rank=i, week=f"2026-03-{i:02d}") for i in range(1, 6)]
    rows += [
        _row("EFFORT_RESULT+SUPPLY_COMING_IN", rank=i, week=f"2024-09-{i:02d}")
        for i in range(1, 6)
    ]

    report = compile_manual_review_evidence(rows, min_approved_examples_per_target=5)

    assert report["target_count"] == 2
    assert report["approved_target_count"] == 2
    assert [row["target"] for row in report["targets"]] == [
        "EFFORT_RESULT+SUPPLY_COMING_IN",
        "RESULT_GT_EFFORT",
    ]


def test_missing_reviewer_and_date_block_approval() -> None:
    rows = [
        _row(rank=i, week=f"2026-03-{i:02d}", reviewer="", review_date="")
        for i in range(1, 6)
    ]

    report = compile_manual_review_evidence(rows, min_approved_examples_per_target=5)

    target = report["targets"][0]
    assert target["approved_examples"] == 0
    assert "has_minimum_approved_examples" in target["failed_evidence_checks"]
    assert "reviewer_recorded" in target["failed_evidence_checks"]
    assert "review_date_recorded" in target["failed_evidence_checks"]


def test_loader_reads_filled_csv_rows(tmp_path: Path) -> None:
    path = tmp_path / "manual_review.csv"
    rows = [_row(rank=1), _row(rank=2)]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    loaded = load_review_rows_csv(path)

    assert loaded == rows


def test_markdown_renderer_includes_boundary_and_target_status() -> None:
    rows = [_row(rank=i, week=f"2026-03-{i:02d}") for i in range(1, 6)]
    report = compile_manual_review_evidence(rows, min_approved_examples_per_target=5)

    rendered = render_manual_review_evidence_markdown(report)

    assert "# Effort/Result Manual Review Evidence" in rendered
    assert "Production change allowed: false" in rendered
    assert "`approved_for_calibration_experiment`" in rendered


def test_cli_writes_json_output(tmp_path: Path) -> None:
    input_path = tmp_path / "manual_review.csv"
    output_path = tmp_path / "evidence.json"
    rows = [_row(rank=i, week=f"2026-03-{i:02d}") for i in range(1, 6)]
    with input_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.compile_effort_result_manual_review_evidence",
            str(input_path),
            "--min-approved-examples-per-target",
            "5",
            "--format",
            "json",
            "--output",
            str(output_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout == ""
    parsed = json.loads(output_path.read_text(encoding="utf-8"))
    assert parsed["gate_evidence_ready"] is True


def test_positive_minimum_is_required() -> None:
    with pytest.raises(ValueError):
        compile_manual_review_evidence([], min_approved_examples_per_target=0)
