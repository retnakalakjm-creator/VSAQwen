import json
from pathlib import Path

import pytest

from audit.index_effort_result_visual_replay_shadow_validation_package import (
    BLOCKED_DECISION,
    BLOCKED_STATUS,
    DEFAULT_MIN_PACKAGE_CASES,
    READY_DECISION,
    READY_STATUS,
    index_effort_result_visual_replay_shadow_validation_package,
    main,
    render_effort_result_visual_replay_shadow_validation_package_index_markdown,
)

PENDING_SOURCE = Path("audit/fixtures/effort_result_visual_replay_shadow_integration_gate_pending.json")
PENDING_FIXTURE = Path("audit/fixtures/effort_result_visual_replay_shadow_validation_package_index_pending.json")


def _integration_case(
    case_id: str,
    *,
    outcome: str = "pass",
    accepted: bool = True,
    evidence: str = "audit/evidence/lt-shadow-review.png",
    reviewer: str = "manual-reviewer",
    reviewed_at: str = "2026-09-14T09:00:00+05:30",
    production_blocked: bool = True,
    blockers: list[str] | None = None,
) -> dict[str, object]:
    symbol, week, target = case_id.split("|")
    return {
        "case_id": case_id,
        "symbol": symbol,
        "event_week_beginning": week,
        "target": target,
        "review_outcome": outcome,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at,
        "evidence_artifact": evidence,
        "shadow_gate_case_accepted": accepted,
        "production_blocked": production_blocked,
        "blockers": blockers or [],
        "audit_only": True,
        "manual_review_only": True,
        "offline_replay_only": True,
        "production_change_allowed": False,
        "automatic_promotion_allowed": False,
    }


def _passed_shadow_gate_report(*, cases: list[dict[str, object]] | None = None) -> dict[str, object]:
    selected = cases or [
        _integration_case("LT.NS|2025-02-24|STRUCTURAL_WEAKENING"),
        _integration_case("LT.NS|2026-03-02|RESULT_GT_EFFORT"),
    ]
    return {
        "report_type": "effort_result_visual_replay_shadow_integration_gate_report",
        "shadow_integration_gate_status": "visual_replay_shadow_integration_gate_passed",
        "shadow_integration_gate_decision": "shadow_visual_replay_validation_passed",
        "shadow_integration_gate_passed": True,
        "shadow_validation_passed": True,
        "downstream_production_blocked": True,
        "allowed_next_step": "open_separate_production_pr_after_manual_approval",
        "blockers": [],
        "integration_cases": selected,
        "audit_only": True,
        "manual_review_only": True,
        "offline_replay_only": True,
        "production_change_allowed": False,
        "automatic_promotion_allowed": False,
    }


def test_all_pass_shadow_gate_creates_ready_package_index() -> None:
    report = index_effort_result_visual_replay_shadow_validation_package(_passed_shadow_gate_report())

    assert report["report_type"] == "effort_result_visual_replay_shadow_validation_package_index"
    assert report["validation_package_index_status"] == READY_STATUS
    assert report["validation_package_index_decision"] == READY_DECISION
    assert report["validation_package_index_ready"] is True
    assert report["shadow_validation_passed"] is True
    assert report["downstream_production_blocked"] is True
    assert report["allowed_next_step"] == "prepare_separate_production_pr_review_packet"
    assert report["selected_case_count"] == 2
    assert report["ready_case_count"] == DEFAULT_MIN_PACKAGE_CASES
    assert report["evidence_artifact_count"] == 2
    assert report["blockers"] == []
    assert all(case["package_case_ready"] is True for case in report["package_cases"])
    assert report["automatic_promotion_allowed"] is False
    assert report["production_change_allowed"] is False
    assert report["requires_separate_production_pr"] is True


def test_pending_shadow_gate_fixture_stays_blocked() -> None:
    fixture = json.loads(PENDING_FIXTURE.read_text(encoding="utf-8"))

    assert fixture["validation_package_index_status"] == BLOCKED_STATUS
    assert fixture["validation_package_index_decision"] == BLOCKED_DECISION
    assert fixture["validation_package_index_ready"] is False
    assert fixture["shadow_validation_passed"] is False
    assert fixture["downstream_production_blocked"] is True
    assert fixture["selected_case_count"] == 2
    assert fixture["ready_case_count"] == 0
    assert fixture["evidence_artifact_count"] == 0
    assert fixture["undecided_case_count"] == 2
    assert "undecided_package_cases_present" in fixture["blockers"]
    assert all(case["package_case_ready"] is False for case in fixture["package_cases"])


def test_pending_fixture_matches_current_shadow_gate_pending_source() -> None:
    source = json.loads(PENDING_SOURCE.read_text(encoding="utf-8"))
    expected = json.loads(PENDING_FIXTURE.read_text(encoding="utf-8"))

    assert index_effort_result_visual_replay_shadow_validation_package(source) == expected


def test_failed_case_blocks_package_index_even_if_source_gate_claims_passed() -> None:
    source = _passed_shadow_gate_report(
        cases=[
            _integration_case("LT.NS|2025-02-24|STRUCTURAL_WEAKENING"),
            _integration_case("LT.NS|2026-03-02|RESULT_GT_EFFORT", outcome="fail"),
        ]
    )

    report = index_effort_result_visual_replay_shadow_validation_package(source)

    assert report["validation_package_index_ready"] is False
    assert "failed_package_cases_present" in report["blockers"]
    assert "package_case_blockers_present" in report["blockers"]
    assert report["failed_case_count"] == 1
    assert report["downstream_production_blocked"] is True


def test_missing_case_evidence_blocks_package_index() -> None:
    source = _passed_shadow_gate_report(
        cases=[
            _integration_case("LT.NS|2025-02-24|STRUCTURAL_WEAKENING"),
            _integration_case("LT.NS|2026-03-02|RESULT_GT_EFFORT", evidence=""),
        ]
    )

    report = index_effort_result_visual_replay_shadow_validation_package(source)

    assert report["validation_package_index_ready"] is False
    assert "not_enough_ready_package_cases" in report["blockers"]
    assert "package_case_blockers_present" in report["blockers"]
    assert "missing_case_evidence_artifact" in report["package_cases"][1]["blockers"]


def test_unblocked_production_case_blocks_package_index() -> None:
    source = _passed_shadow_gate_report(
        cases=[
            _integration_case("LT.NS|2025-02-24|STRUCTURAL_WEAKENING"),
            _integration_case("LT.NS|2026-03-02|RESULT_GT_EFFORT", production_blocked=False),
        ]
    )

    report = index_effort_result_visual_replay_shadow_validation_package(source)

    assert report["validation_package_index_ready"] is False
    assert "case_production_boundary_not_blocked" in report["package_cases"][1]["blockers"]
    assert "package_case_blockers_present" in report["blockers"]


def test_unsafe_source_flag_blocks_package_index() -> None:
    source = _passed_shadow_gate_report()
    source["include_in_scoring"] = True

    report = index_effort_result_visual_replay_shadow_validation_package(source)

    assert report["validation_package_index_ready"] is False
    assert "source_production_boundary_open" in report["blockers"]


def test_missing_required_package_artifact_blocks_index() -> None:
    source = _passed_shadow_gate_report()
    report = index_effort_result_visual_replay_shadow_validation_package(
        source,
        package_artifacts=[
            {
                "artifact_id": "shadow_gate_report",
                "path": "",
                "required": True,
                "description": "missing path should block",
            }
        ],
    )

    assert report["validation_package_index_ready"] is False
    assert "package_artifact_blockers_present" in report["blockers"]
    assert report["package_artifacts"][0]["artifact_ready"] is False


def test_symbol_filter_selects_matching_cases_only() -> None:
    source = _passed_shadow_gate_report(
        cases=[
            _integration_case("LT.NS|2025-02-24|STRUCTURAL_WEAKENING"),
            _integration_case("RELIANCE.NS|2026-03-02|RESULT_GT_EFFORT"),
        ]
    )

    report = index_effort_result_visual_replay_shadow_validation_package(
        source,
        required_symbols=["RELIANCE.NS"],
        min_package_cases=1,
    )

    assert report["validation_package_index_ready"] is True
    assert report["selected_case_count"] == 1
    assert report["package_cases"][0]["symbol"] == "RELIANCE.NS"


def test_markdown_renders_cases_artifacts_and_manual_steps() -> None:
    report = index_effort_result_visual_replay_shadow_validation_package(_passed_shadow_gate_report())
    markdown = render_effort_result_visual_replay_shadow_validation_package_index_markdown(report)

    assert "# Effort/Result Visual Replay Shadow Validation Package Index" in markdown
    assert "## Package Cases" in markdown
    assert "## Package Artifacts" in markdown
    assert "## Manual Review Steps" in markdown
    assert "open_dev_only_visual_replay_route" in markdown
    assert "LT.NS|2025-02-24|STRUCTURAL_WEAKENING" in markdown
    assert "separate production PR" in markdown


def test_cli_writes_json_and_markdown(tmp_path: Path) -> None:
    source_path = tmp_path / "shadow_gate.json"
    json_output = tmp_path / "package.json"
    markdown_output = tmp_path / "package.md"
    source_path.write_text(json.dumps(_passed_shadow_gate_report()), encoding="utf-8")

    assert main([str(source_path), "--output", str(json_output)]) == 0
    generated = json.loads(json_output.read_text(encoding="utf-8"))
    assert generated["validation_package_index_ready"] is True

    assert main([str(source_path), "--format", "markdown", "--output", str(markdown_output)]) == 0
    assert "Validation Package Index" in markdown_output.read_text(encoding="utf-8")


def test_min_package_cases_must_be_positive() -> None:
    with pytest.raises(ValueError, match="min_package_cases must be positive"):
        index_effort_result_visual_replay_shadow_validation_package(
            _passed_shadow_gate_report(),
            min_package_cases=0,
        )


def test_source_contains_no_live_fetch_or_storage_side_effects() -> None:
    source = Path("audit/index_effort_result_visual_replay_shadow_validation_package.py").read_text(
        encoding="utf-8"
    ).lower()

    forbidden_tokens = [
        "requests.",
        "urllib",
        "httpx",
        "subprocess",
        "sqlite3",
        "socket",
        ".post(",
        ".put(",
        ".delete(",
        "insert into",
        "update signals",
        "place_order",
        "emit_alert",
    ]
    for token in forbidden_tokens:
        assert token not in source
