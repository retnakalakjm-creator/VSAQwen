from __future__ import annotations

import csv
import json
import subprocess
import sys
from io import StringIO
from pathlib import Path

from vsa_audit_candidate_triage import (
    TRIAGE_CLEAN_CANDIDATE,
    TRIAGE_CONTRADICTORY_PRODUCTION,
    TRIAGE_LIKELY_NOISY,
    TRIAGE_OVERLAPPING_CLUSTER,
    TRIAGE_QUALIFICATION_LIFECYCLE,
    build_vsa_audit_candidate_triage,
    render_vsa_audit_candidate_triage_csv,
)


def _candidate(**overrides):
    base = {
        "symbol": "LT.NS",
        "replay_week": "2026-03-02 00:00:00",
        "replay_bar_index": 233,
        "candidate_code": "audit_effort_gt_result_candidate",
        "candidate_family": "effort_vs_result",
        "direction": "bullish_reversal_review",
        "priority": "high",
        "production_status": "not_confirmed_by_current_detector",
        "qualification": "unqualified",
        "target_event_codes": ["demand_coming_in"],
        "scoring_event_codes": ["demand_coming_in"],
        "source_diagnostics": ["review_potential_effort_gt_result"],
        "source_audit_flags": [],
        "reason": "review effort vs result",
        "audit_only": True,
    }
    base.update(overrides)
    return base


def test_candidate_triage_separates_clean_and_contradictory_rows() -> None:
    payload = {
        "audit_only": True,
        "rows": [
            _candidate(),
            _candidate(
                symbol="RELIANCE.NS",
                target_event_codes=["hidden_supply"],
                scoring_event_codes=["hidden_supply"],
            ),
        ],
    }

    triage = build_vsa_audit_candidate_triage(payload).to_dict()

    assert triage["total_input_rows"] == 2
    assert triage["total_triage_rows"] == 2
    assert triage["bucket_counts"] == {
        TRIAGE_CLEAN_CANDIDATE: 1,
        TRIAGE_CONTRADICTORY_PRODUCTION: 1,
    }
    clean = next(row for row in triage["rows"] if row["symbol"] == "LT.NS")
    contradictory = next(row for row in triage["rows"] if row["symbol"] == "RELIANCE.NS")
    assert clean["triage_grade"] == "A"
    assert contradictory["triage_grade"] == "C"
    assert "bearish" in " ".join(contradictory["triage_reasons"])


def test_candidate_triage_groups_same_week_overlapping_clusters() -> None:
    payload = {
        "rows": [
            _candidate(target_event_codes=[], scoring_event_codes=[]),
            _candidate(
                candidate_code="audit_absorption_candidate",
                candidate_family="absorption",
                source_diagnostics=["review_potential_absorption"],
                target_event_codes=[],
                scoring_event_codes=[],
            ),
            _candidate(
                candidate_code="audit_high_volume_reversal_candidate",
                candidate_family="high_volume_reversal",
                source_diagnostics=["review_high_volume_reversal_without_bullish_event"],
                target_event_codes=[],
                scoring_event_codes=[],
            ),
        ]
    }

    triage = build_vsa_audit_candidate_triage(payload).to_dict()

    assert triage["bucket_counts"] == {TRIAGE_OVERLAPPING_CLUSTER: 3}
    assert all(row["cluster_size"] == 3 for row in triage["rows"])
    assert all(len(row["sibling_candidate_families"]) == 2 for row in triage["rows"])


def test_candidate_triage_prioritizes_qualification_lifecycle_conflicts() -> None:
    payload = {
        "rows": [
            _candidate(
                candidate_code="audit_qualification_conflict_candidate",
                candidate_family="qualification_lifecycle",
                direction="context_review",
                qualification="persistent_bearish",
                source_diagnostics=[],
                source_audit_flags=["bullish_vsa_against_bearish_qualification"],
            )
        ]
    }

    triage = build_vsa_audit_candidate_triage(payload).to_dict()

    assert triage["bucket_counts"] == {TRIAGE_QUALIFICATION_LIFECYCLE: 1}
    assert triage["rows"][0]["triage_grade"] == "A"
    assert "lifecycle" in triage["rows"][0]["recommended_action"]


def test_candidate_triage_deprioritizes_redundant_bullish_reversal_candidates() -> None:
    payload = {
        "rows": [
            _candidate(
                symbol="COALINDIA.NS",
                qualification="persistent_bullish",
                target_event_codes=["increasing_demand"],
                scoring_event_codes=["increasing_demand"],
            )
        ]
    }

    triage = build_vsa_audit_candidate_triage(payload).to_dict()

    assert triage["bucket_counts"] == {TRIAGE_LIKELY_NOISY: 1}
    assert triage["rows"][0]["triage_grade"] == "D"


def test_candidate_triage_csv_renders_bucket_columns() -> None:
    triage = build_vsa_audit_candidate_triage({"rows": [_candidate()]})

    body = render_vsa_audit_candidate_triage_csv(triage)
    rows = list(csv.DictReader(StringIO(body)))

    assert len(rows) == 1
    assert rows[0]["symbol"] == "LT.NS"
    assert rows[0]["triage_bucket"] == TRIAGE_CLEAN_CANDIDATE
    assert rows[0]["triage_grade"] == "A"


def test_candidate_triage_cli_writes_json_and_csv(tmp_path: Path) -> None:
    input_file = tmp_path / "standard_basket_review.json"
    json_output = tmp_path / "standard_basket_triage.json"
    csv_output = tmp_path / "standard_basket_triage.csv"
    input_file.write_text(json.dumps({"rows": [_candidate()]}), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/vsa_audit_candidate_triage.py",
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
    assert json_body["bucket_counts"] == {TRIAGE_CLEAN_CANDIDATE: 1}
    assert csv_rows[0]["triage_bucket"] == TRIAGE_CLEAN_CANDIDATE
