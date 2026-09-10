from __future__ import annotations

import csv
import json
import subprocess
import sys
from io import StringIO
from pathlib import Path

from vsa_event_causality_diagnostics import (
    OUTCOME_FOLLOW_THROUGH_VISIBLE,
    OUTCOME_INVALIDATED_BY_LATER_EVIDENCE,
    OUTCOME_LIFECYCLE_TRANSITION_REVIEW,
    OUTCOME_PENDING_INSUFFICIENT_FUTURE_ROWS,
    build_vsa_event_causality_diagnostics,
    render_vsa_event_causality_diagnostics_csv,
)


def _row(**overrides):
    base = {
        "symbol": "LT.NS",
        "replay_week": "2026-03-02 00:00:00",
        "replay_bar_index": 233,
        "candidate_code": "stopping_volume",
        "candidate_family": "demand",
        "direction": "bullish",
        "priority": "high",
        "qualification": "unqualified",
        "target_event_codes": ["stopping_volume"],
        "scoring_event_codes": ["stopping_volume"],
        "triage_reasons": ["review demand event"],
        "audit_only": True,
    }
    base.update(overrides)
    return base


def test_causality_marks_same_side_follow_through_visible() -> None:
    payload = {
        "rows": [
            _row(candidate_code="stopping_volume", target_event_codes=["stopping_volume"]),
            _row(
                replay_week="2026-03-23 00:00:00",
                replay_bar_index=236,
                candidate_code="demand_coming_in",
                target_event_codes=["demand_coming_in"],
                scoring_event_codes=["demand_coming_in"],
            ),
        ]
    }

    summary = build_vsa_event_causality_diagnostics(payload, review_horizon_rows=4).to_dict()

    first = next(row for row in summary["rows"] if row["event_code"] == "stopping_volume")
    assert first["outcome_label"] == OUTCOME_FOLLOW_THROUGH_VISIBLE
    assert first["future_supporting_event_codes"] == ["demand_coming_in"]
    assert summary["outcome_counts"][OUTCOME_FOLLOW_THROUGH_VISIBLE] == 1


def test_causality_marks_later_opposing_vsa_as_invalidation_review() -> None:
    payload = {
        "rows": [
            _row(
                replay_week="2025-03-24 00:00:00",
                replay_bar_index=180,
                candidate_code="structural_progression_weakening",
                candidate_family="structural_progression",
                direction="bearish",
                target_event_codes=["structural_progression_weakening"],
                scoring_event_codes=["structural_progression_weakening"],
            ),
            _row(
                replay_week="2025-04-07 00:00:00",
                replay_bar_index=182,
                candidate_code="spring",
                candidate_family="spring",
                direction="bullish",
                target_event_codes=["spring"],
                scoring_event_codes=["spring"],
            ),
        ]
    }

    summary = build_vsa_event_causality_diagnostics(payload, review_horizon_rows=4).to_dict()

    structural = next(row for row in summary["rows"] if row["event_code"] == "structural_progression_weakening")
    assert structural["outcome_label"] == OUTCOME_INVALIDATED_BY_LATER_EVIDENCE
    assert structural["future_opposing_event_codes"] == ["spring"]
    assert "contradicted" in structural["causal_read"]


def test_causality_marks_lifecycle_transition_rows_separately() -> None:
    payload = {
        "rows": [
            _row(
                candidate_code="invalidate_qualification",
                candidate_family="qualification_lifecycle",
                direction="context_review",
                proposed_action="invalidate_qualification",
                lifecycle_status="invalidated_review",
                target_event_codes=["demand_coming_in"],
                scoring_event_codes=["demand_coming_in"],
            )
        ]
    }

    summary = build_vsa_event_causality_diagnostics(payload).to_dict()

    assert summary["rows"][0]["outcome_label"] == OUTCOME_LIFECYCLE_TRANSITION_REVIEW
    assert summary["rows"][0]["recommended_action"] == "review_context_lifecycle_transition"


def test_causality_marks_latest_event_as_pending_when_future_rows_missing() -> None:
    payload = {"rows": [_row(candidate_code="spring", target_event_codes=["spring"])]}

    summary = build_vsa_event_causality_diagnostics(payload, review_horizon_rows=3).to_dict()

    assert summary["rows"][0]["outcome_label"] == OUTCOME_PENDING_INSUFFICIENT_FUTURE_ROWS
    assert summary["rows"][0]["future_rows_checked"] == 0


def test_causality_csv_renders_outcome_columns() -> None:
    summary = build_vsa_event_causality_diagnostics({"rows": [_row()]})

    body = render_vsa_event_causality_diagnostics_csv(summary)
    rows = list(csv.DictReader(StringIO(body)))

    assert len(rows) == 1
    assert rows[0]["symbol"] == "LT.NS"
    assert rows[0]["outcome_label"] == OUTCOME_PENDING_INSUFFICIENT_FUTURE_ROWS
    assert "causal_read" in rows[0]


def test_causality_cli_writes_json_and_csv(tmp_path: Path) -> None:
    input_file = tmp_path / "standard_basket_triage.json"
    json_output = tmp_path / "standard_basket_causality.json"
    csv_output = tmp_path / "standard_basket_causality.csv"
    input_file.write_text(json.dumps({"rows": [_row()]}), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/vsa_event_causality_diagnostics.py",
            str(input_file),
            "--json-output",
            str(json_output),
            "--csv-output",
            str(csv_output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    json_body = json.loads(json_output.read_text(encoding="utf-8"))
    csv_rows = list(csv.DictReader(StringIO(csv_output.read_text(encoding="utf-8"))))
    assert json_body["outcome_counts"] == {OUTCOME_PENDING_INSUFFICIENT_FUTURE_ROWS: 1}
    assert csv_rows[0]["outcome_label"] == OUTCOME_PENDING_INSUFFICIENT_FUTURE_ROWS
