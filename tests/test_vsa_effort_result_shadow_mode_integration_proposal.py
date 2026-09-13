import json
import subprocess
import sys
from pathlib import Path

import pytest

from audit.propose_effort_result_shadow_mode_integration import (
    GATE_READY_STATUS,
    REPORT_TYPE,
    SHADOW_PROPOSAL_BLOCKED_STATUS,
    SHADOW_PROPOSAL_READY_STATUS,
    build_shadow_mode_integration_proposal,
    render_shadow_mode_integration_markdown,
)


def _gate(target, *, ready=True, examples=5):
    if ready:
        return {
            "target": target,
            "gate_status": GATE_READY_STATUS,
            "manual_review_status": "approved_for_calibration_experiment",
            "reviewer": "ProVSA",
            "review_date": "2026-09-13",
            "reviewed_examples": examples,
            "reviewed_symbols": ["ETERNAL.NS"],
            "reviewed_weeks": ["2024-03-04"],
        }
    return {
        "target": target,
        "gate_status": "blocked_pending_manual_review_evidence",
        "manual_review_status": "needs_more_review",
        "reviewed_examples": examples,
        "reviewed_symbols": [],
        "reviewed_weeks": [],
    }


def test_builds_ready_shadow_mode_proposal_for_passed_gate_targets():
    report = build_shadow_mode_integration_proposal(
        {
            "report_type": "effort_result_calibration_proposal_gate",
            "gate_status": GATE_READY_STATUS,
            "target_gates": [
                _gate("RESULT_GT_EFFORT", examples=5),
                _gate("EFFORT_RESULT+SUPPLY_COMING_IN", examples=7),
            ],
        }
    )

    assert report["report_type"] == REPORT_TYPE
    assert report["proposal_status"] == SHADOW_PROPOSAL_READY_STATUS
    assert report["ready_target_count"] == 2
    assert report["blocked_target_count"] == 0
    assert report["next_stage"] == "separate_shadow_mode_pr_review"
    assert report["production_change_allowed"] is False
    assert report["shadow_mode_only"] is True
    assert report["may_change_scoring"] is False
    assert report["may_activate_detector"] is False
    assert report["may_change_api"] is False
    assert report["may_change_frontend"] is False


def test_blocks_target_when_gate_has_not_passed():
    report = build_shadow_mode_integration_proposal(
        {
            "report_type": "effort_result_calibration_proposal_gate",
            "gate_status": "needs_attention",
            "target_gates": [_gate("RESULT_GT_EFFORT", ready=False)],
        }
    )

    target = report["target_proposals"][0]
    assert report["proposal_status"] == "needs_attention"
    assert target["proposal_status"] == SHADOW_PROPOSAL_BLOCKED_STATUS
    assert "gate_ready" in target["blockers"]
    assert target["shadow_mode_observation"]["emit_observation"] is False


def test_blocks_target_when_reviewed_examples_are_below_threshold():
    report = build_shadow_mode_integration_proposal(
        {
            "report_type": "effort_result_calibration_proposal_gate",
            "gate_status": GATE_READY_STATUS,
            "target_gates": [_gate("RESULT_GT_EFFORT", examples=4)],
        },
        min_reviewed_examples_per_target=5,
    )

    target = report["target_proposals"][0]
    assert target["proposal_status"] == SHADOW_PROPOSAL_BLOCKED_STATUS
    assert "minimum_reviewed_examples" in target["blockers"]


def test_accepts_gate_shape_with_nested_manual_review_evidence():
    report = build_shadow_mode_integration_proposal(
        {
            "report_type": "effort_result_calibration_proposal_gate",
            "gate_status": GATE_READY_STATUS,
            "target_gates": [
                {
                    "target": "EFFORT_RESULT+SUPPLY_COMING_IN",
                    "gate_status": GATE_READY_STATUS,
                    "manual_review_evidence": {
                        "manual_review_status": "approved_for_calibration_experiment",
                        "reviewer": "ProVSA",
                        "review_date": "2026-09-13",
                        "reviewed_examples": 7,
                        "reviewed_symbols": ["GODREJPROP.NS", "HDFCBANK.NS"],
                        "reviewed_weeks": ["2024-09-23"],
                    },
                }
            ],
        }
    )

    target = report["target_proposals"][0]
    assert target["proposal_status"] == SHADOW_PROPOSAL_READY_STATUS
    assert target["reviewed_examples"] == 7
    assert target["reviewed_symbols"] == ["GODREJPROP.NS", "HDFCBANK.NS"]


def test_assigns_default_roles_for_known_targets():
    report = build_shadow_mode_integration_proposal(
        {
            "gate_status": GATE_READY_STATUS,
            "target_gates": [
                _gate("RESULT_GT_EFFORT"),
                _gate("EFFORT_RESULT+SUPPLY_COMING_IN"),
            ],
        }
    )

    roles = {row["target"]: row["shadow_signal_role"] for row in report["target_proposals"]}
    assert roles["RESULT_GT_EFFORT"] == "direction_sensitive_shadow_observation"
    assert roles["EFFORT_RESULT+SUPPLY_COMING_IN"] == "bearish_shadow_observation"


def test_all_ready_targets_are_in_integration_contract():
    report = build_shadow_mode_integration_proposal(
        {
            "gate_status": GATE_READY_STATUS,
            "target_gates": [
                _gate("RESULT_GT_EFFORT"),
                _gate("EFFORT_RESULT+SUPPLY_COMING_IN", examples=7),
            ],
        }
    )

    contract = report["integration_contract"]
    assert contract["ready_targets"] == [
        "RESULT_GT_EFFORT",
        "EFFORT_RESULT+SUPPLY_COMING_IN",
    ]
    assert "production_scoring" in contract["must_remain_disabled_for"]
    assert contract["production_change_allowed"] is False


def test_markdown_renderer_mentions_shadow_boundary_and_targets():
    report = build_shadow_mode_integration_proposal(
        {
            "gate_status": GATE_READY_STATUS,
            "target_gates": [_gate("RESULT_GT_EFFORT")],
        }
    )
    markdown = render_shadow_mode_integration_markdown(report)

    assert "# Effort/Result Shadow-Mode Integration Proposal" in markdown
    assert "Shadow mode only: true" in markdown
    assert "`RESULT_GT_EFFORT`" in markdown
    assert "May change scoring: false" in markdown


def test_cli_reads_gate_json_and_writes_markdown(tmp_path):
    gate_path = tmp_path / "gate.json"
    out_path = tmp_path / "proposal.md"
    gate_path.write_text(
        json.dumps(
            {
                "report_type": "effort_result_calibration_proposal_gate",
                "gate_status": GATE_READY_STATUS,
                "target_gates": [_gate("RESULT_GT_EFFORT")],
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "audit.propose_effort_result_shadow_mode_integration",
            str(gate_path),
            "--format",
            "markdown",
            "--output",
            str(out_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "RESULT_GT_EFFORT" in out_path.read_text(encoding="utf-8")


def test_rejects_non_positive_minimum():
    with pytest.raises(ValueError):
        build_shadow_mode_integration_proposal(
            {"target_gates": []},
            min_reviewed_examples_per_target=0,
        )
