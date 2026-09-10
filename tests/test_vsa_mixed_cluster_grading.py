from __future__ import annotations

import csv
import json
import subprocess
import sys
from io import StringIO
from pathlib import Path

from vsa_mixed_cluster_grading import (
    ACTION_REVIEW_DETECTOR_GATES,
    ACTION_REVIEW_LIFECYCLE_INVALIDATION,
    ACTION_REVIEW_SUPPLY_WARNING,
    GRADE_A,
    GRADE_B,
    REVIEW_BEARISH_CONTEXT_DEMAND_REVERSAL_CLUSTER,
    REVIEW_BULLISH_CONTEXT_SUPPLY_WARNING_CLUSTER,
    REVIEW_UNQUALIFIED_BIDIRECTIONAL_DETECTOR_CONFLICT,
    build_vsa_mixed_cluster_grading,
    render_vsa_mixed_cluster_grading_csv,
)


def _cluster(**overrides):
    base = {
        "audit_only": True,
        "symbol": "LT.NS",
        "cluster_id": "LT.NS:233-236",
        "start_week": "2026-03-02 00:00:00",
        "end_week": "2026-03-23 00:00:00",
        "start_bar_index": 233,
        "end_bar_index": 236,
        "row_count": 5,
        "event_families": ["absorption", "effort_vs_result", "high_volume_reversal"],
        "event_codes": [
            "audit_absorption_candidate",
            "audit_effort_gt_result_candidate",
            "audit_high_volume_reversal_candidate",
        ],
        "qualifications": ["persistent_bearish"],
        "supporting_event_codes": ["demand_coming_in", "increasing_demand"],
        "opposing_event_codes": ["structural_progression_weakening", "increasing_supply"],
        "source_buckets": [
            "overlapping_candidate_cluster",
            "contradictory_production_evidence",
            "clean_candidate",
        ],
    }
    base.update(overrides)
    return base


def test_grading_identifies_bearish_context_demand_reversal_cluster() -> None:
    summary = build_vsa_mixed_cluster_grading({"clusters": [_cluster()]}).to_dict()

    row = summary["rows"][0]
    assert row["grade"] == GRADE_A
    assert row["review_type"] == REVIEW_BEARISH_CONTEXT_DEMAND_REVERSAL_CLUSTER
    assert row["recommended_action"] == ACTION_REVIEW_LIFECYCLE_INVALIDATION
    assert "persistent bearish qualification" in row["grading_reasons"][0]
    assert summary["review_type_counts"] == {REVIEW_BEARISH_CONTEXT_DEMAND_REVERSAL_CLUSTER: 1}


def test_grading_identifies_bullish_context_supply_warning_cluster() -> None:
    summary = build_vsa_mixed_cluster_grading(
        {
            "clusters": [
                _cluster(
                    symbol="TCS.NS",
                    cluster_id="TCS.NS:236-236",
                    start_bar_index=236,
                    end_bar_index=236,
                    row_count=2,
                    event_families=["absorption", "high_volume_reversal"],
                    qualifications=["persistent_bullish"],
                    supporting_event_codes=["increasing_demand"],
                    opposing_event_codes=["increasing_supply"],
                    source_buckets=["contradictory_production_evidence"],
                )
            ]
        }
    ).to_dict()

    row = summary["rows"][0]
    assert row["review_type"] == REVIEW_BULLISH_CONTEXT_SUPPLY_WARNING_CLUSTER
    assert row["recommended_action"] == ACTION_REVIEW_SUPPLY_WARNING
    assert row["grade"] in {GRADE_A, GRADE_B}


def test_grading_identifies_unqualified_bidirectional_detector_conflict() -> None:
    summary = build_vsa_mixed_cluster_grading(
        {
            "clusters": [
                _cluster(
                    symbol="AXISBANK.NS",
                    cluster_id="AXISBANK.NS:1425-1427",
                    start_bar_index=1425,
                    end_bar_index=1427,
                    row_count=6,
                    qualifications=["unqualified"],
                    supporting_event_codes=["increasing_demand", "demand_coming_in"],
                    opposing_event_codes=["hidden_supply", "buying_climax", "upthrust"],
                    source_buckets=["contradictory_production_evidence", "overlapping_candidate_cluster"],
                )
            ]
        }
    ).to_dict()

    row = summary["rows"][0]
    assert row["review_type"] == REVIEW_UNQUALIFIED_BIDIRECTIONAL_DETECTOR_CONFLICT
    assert row["recommended_action"] == ACTION_REVIEW_DETECTOR_GATES
    assert row["grade"] == GRADE_A


def test_grading_orders_top_priority_clusters_by_score() -> None:
    summary = build_vsa_mixed_cluster_grading(
        {
            "clusters": [
                _cluster(symbol="HINDUNILVR.NS", cluster_id="HINDUNILVR.NS:238-238", row_count=1, event_families=["effort_vs_result"], qualifications=["unqualified"], supporting_event_codes=["increasing_demand"], opposing_event_codes=["hidden_supply"], source_buckets=["clean_candidate"], start_bar_index=238, end_bar_index=238),
                _cluster(),
            ]
        }
    ).to_dict()

    assert summary["total_input_clusters"] == 2
    assert summary["total_graded_clusters"] == 2
    assert summary["top_priority_clusters"][0]["symbol"] == "LT.NS"
    assert summary["top_priority_clusters"][0]["grade"] == GRADE_A


def test_grading_csv_renders_review_columns() -> None:
    summary = build_vsa_mixed_cluster_grading({"clusters": [_cluster()]})

    body = render_vsa_mixed_cluster_grading_csv(summary)
    rows = list(csv.DictReader(StringIO(body)))

    assert len(rows) == 1
    assert rows[0]["symbol"] == "LT.NS"
    assert rows[0]["grade"] == GRADE_A
    assert rows[0]["review_type"] == REVIEW_BEARISH_CONTEXT_DEMAND_REVERSAL_CLUSTER
    assert "cluster_read" in rows[0]


def test_grading_cli_writes_json_and_csv(tmp_path: Path) -> None:
    input_file = tmp_path / "standard_basket_mixed_clusters.json"
    json_output = tmp_path / "standard_basket_mixed_cluster_grades.json"
    csv_output = tmp_path / "standard_basket_mixed_cluster_grades.csv"
    input_file.write_text(json.dumps({"clusters": [_cluster()]}), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/vsa_mixed_cluster_grading.py",
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
    assert json_body["grade_counts"] == {GRADE_A: 1}
    assert csv_rows[0]["recommended_action"] == ACTION_REVIEW_LIFECYCLE_INVALIDATION
