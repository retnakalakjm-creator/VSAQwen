from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from qualification_lifecycle_labels import QualificationLifecycleLabel
from vsa_absorption_background_labels import AbsorptionBackgroundReviewLabel
from vsa_plain_english_legends import (
    LEGEND_REGISTRY,
    LegendFamily,
    chronological_reading_cycle,
    explain_legend,
    explain_legend_codes,
    explain_legend_for_field,
    family_for_field,
    get_plain_english_legend,
    legend_registry_json,
    legend_registry_payload,
    registry_by_family,
)
from vsa_recovery_sequence_labels import RecoverySequenceReviewLabel


def test_registry_has_required_plain_english_fields_for_every_entry() -> None:
    assert LEGEND_REGISTRY
    seen: set[tuple[str, str]] = set()
    for legend in LEGEND_REGISTRY:
        key = (legend.family.value, legend.code)
        assert key not in seen
        seen.add(key)
        payload = legend.to_dict()
        assert payload["code"]
        assert payload["family"]
        assert payload["frontend_label"]
        assert payload["plain_english"]
        assert payload["chronological_stage"]
        assert isinstance(payload["chart_reading_order"], int)
        assert payload["chart_reading_role"]
        assert payload["example_read"]
        assert payload["user_action"]
        assert payload["production_safe"] is True


def test_registry_covers_lifecycle_6c_and_6d_status_constants() -> None:
    for status in QualificationLifecycleLabel:
        legend = get_plain_english_legend(status.value, family=LegendFamily.LIFECYCLE)
        assert legend is not None
        assert legend.plain_english

    for status in RecoverySequenceReviewLabel:
        legend = get_plain_english_legend(status.value, family=LegendFamily.REVIEW_MARKER)
        assert legend is not None
        assert legend.plain_english

    for status in AbsorptionBackgroundReviewLabel:
        legend = get_plain_english_legend(status.value, family=LegendFamily.REVIEW_MARKER)
        assert legend is not None
        assert legend.plain_english


def test_field_aliases_explain_user_mentioned_helper_names() -> None:
    assert family_for_field("_outcome_label") is LegendFamily.OUTCOME
    assert family_for_field("_review_reason") is LegendFamily.REVIEW_REASON
    assert family_for_field("_classify_cluster") is LegendFamily.CLUSTER
    assert family_for_field("_classify_transition") is LegendFamily.TRANSITION
    assert family_for_field("_case_type_for_transition") is LegendFamily.CASE_TYPE

    outcome = explain_legend_for_field("_outcome_label", "follow_through")
    assert outcome["family"] == "outcome_label"
    assert outcome["frontend_label"] == "Follow-Through"
    assert "Later bars supported" in outcome["plain_english"]

    review_reason = explain_legend_for_field("_review_reason", "diagnostic_only")
    assert review_reason["family"] == "review_reason"
    assert "not production evidence" in review_reason["plain_english"]

    cluster = explain_legend_for_field("_classify_cluster", "overlapping_event_conflict")
    assert cluster["family"] == "cluster"
    assert "Bullish and bearish clues overlap" in cluster["plain_english"]

    transition = explain_legend_for_field(
        "_classify_transition",
        "chart_review_conflict_before_invalidation_or_supersession",
    )
    assert transition["family"] == "transition"
    assert "reviewed before invalidating" in transition["plain_english"]

    case_type = explain_legend_for_field(
        "_case_type_for_transition",
        "chart_confirm_supersession_rule_candidate",
    )
    assert case_type["family"] == "case_type"
    assert case_type["frontend_label"] == "Chart-Confirm Supersession Rule Candidate"
    assert "supersede the old background" in case_type["plain_english"]


def test_duplicate_code_none_is_resolved_by_family() -> None:
    lifecycle_none = explain_legend("none", family=LegendFamily.CURRENT_BIAS)
    marker_none = explain_legend("none", family=LegendFamily.REVIEW_MARKER)

    assert lifecycle_none["frontend_label"] == "No Current VSA Bias"
    assert marker_none["frontend_label"] == "No Review Marker"
    assert lifecycle_none["plain_english"] != marker_none["plain_english"]


def test_unknown_legend_gets_safe_frontend_fallback() -> None:
    payload = explain_legend("new_future_code", family="review_reason")

    assert payload["code"] == "new_future_code"
    assert payload["family"] == "review_reason"
    assert payload["frontend_label"] == "New Future Code"
    assert "No plain-English explanation" in payload["plain_english"]
    assert payload["chart_reading_order"] == 99


def test_chronological_cycle_is_frontend_ready() -> None:
    cycle = chronological_reading_cycle()

    assert [item["order"] for item in cycle] == sorted(item["order"] for item in cycle)
    assert cycle[0]["stage"] == "background_mood"
    assert cycle[-1]["stage"] == "review_marker"
    assert any("One candle is a word" in item["plain_english"] for item in cycle)


def test_registry_payload_and_json_are_serializable() -> None:
    payload = legend_registry_payload()
    json_text = legend_registry_json()
    decoded = json.loads(json_text)

    assert payload["production_safe"] is True
    assert decoded["production_safe"] is True
    assert decoded["chart_reading_cycle"]
    assert decoded["field_family_aliases"]["_outcome_label"] == "outcome_label"
    assert any(
        item["code"] == "absorption_background_review"
        and item["plain_english"].startswith("Selling pressure may be getting absorbed")
        for item in decoded["legends"]
    )


def test_registry_by_family_and_many_code_explanations_are_stable() -> None:
    grouped = registry_by_family()
    assert "lifecycle" in grouped
    assert "review_marker" in grouped

    explanations = explain_legend_codes(
        ["absorption_background_review", "active"],
    )
    assert explanations[0]["code"] == "active"
    assert explanations[-1]["code"] == "absorption_background_review"


def test_plain_english_legend_cli_runs_from_repo_root(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    output_path = tmp_path / "legend_registry.json"

    subprocess.run(
        [
            sys.executable,
            "scripts/vsa_plain_english_legends.py",
            "--output",
            str(output_path),
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["field_family_aliases"]["_review_reason"] == "review_reason"
    assert any(item["code"] == "pending_supersession" for item in payload["legends"])
