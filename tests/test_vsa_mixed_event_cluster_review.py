from __future__ import annotations

import csv
import json
import subprocess
import sys
from io import StringIO
from pathlib import Path

from vsa_mixed_event_cluster_review import (
    MIXED_OUTCOME_LABEL,
    build_vsa_mixed_event_cluster_review,
    render_vsa_mixed_event_cluster_review_csv,
)


def _mixed_row(**overrides):
    base = {
        "audit_only": True,
        "symbol": "LT.NS",
        "replay_week": "2026-03-02 00:00:00",
        "replay_bar_index": 233,
        "event_code": "audit_effort_gt_result_candidate",
        "event_family": "effort_vs_result",
        "event_direction": "bullish",
        "qualification": "persistent_bearish",
        "source_bucket": "overlapping_candidate_cluster",
        "outcome_label": MIXED_OUTCOME_LABEL,
        "future_supporting_event_codes": ["demand_coming_in", "increasing_demand"],
        "future_opposing_event_codes": ["structural_progression_weakening", "increasing_supply"],
        "future_lifecycle_actions": [],
    }
    base.update(overrides)
    return base


def test_cluster_review_groups_nearby_same_symbol_mixed_rows() -> None:
    payload = {
        "rows": [
            _mixed_row(
                event_code="audit_absorption_candidate",
                event_family="absorption",
            ),
            _mixed_row(
                replay_week="2026-03-16 00:00:00",
                replay_bar_index=235,
                event_code="audit_high_volume_reversal_candidate",
                event_family="high_volume_reversal",
                future_supporting_event_codes=["demand_coming_in"],
                future_opposing_event_codes=["increasing_supply"],
            ),
        ]
    }

    summary = build_vsa_mixed_event_cluster_review(payload, max_gap_rows=2).to_dict()

    assert summary["total_input_rows"] == 2
    assert summary["total_mixed_rows"] == 2
    assert summary["total_clusters"] == 1
    cluster = summary["clusters"][0]
    assert cluster["cluster_id"] == "LT.NS:233-235"
    assert cluster["row_count"] == 2
    assert cluster["event_families"] == ["absorption", "high_volume_reversal"]
    assert cluster["supporting_event_codes"] == ["demand_coming_in", "increasing_demand"]
    assert cluster["opposing_event_codes"] == ["structural_progression_weakening", "increasing_supply"]
    assert cluster["recommended_action"] == "review_grouped_mixed_cluster_before_rule_change"
    assert "Review the sequence as one cluster" in cluster["causal_read"]


def test_cluster_review_splits_same_symbol_rows_outside_gap() -> None:
    payload = {
        "rows": [
            _mixed_row(replay_bar_index=233),
            _mixed_row(replay_bar_index=238, replay_week="2026-04-06 00:00:00"),
        ]
    }

    summary = build_vsa_mixed_event_cluster_review(payload, max_gap_rows=2).to_dict()

    assert summary["total_clusters"] == 2
    assert [cluster["cluster_id"] for cluster in summary["clusters"]] == [
        "LT.NS:233-233",
        "LT.NS:238-238",
    ]


def test_cluster_review_ignores_non_mixed_rows_and_groups_by_symbol() -> None:
    payload = {
        "rows": [
            _mixed_row(symbol="LT.NS", replay_bar_index=233),
            _mixed_row(
                symbol="LT.NS",
                replay_bar_index=234,
                outcome_label="follow_through_visible",
            ),
            _mixed_row(symbol="RELIANCE.NS", replay_bar_index=233),
        ]
    }

    summary = build_vsa_mixed_event_cluster_review(payload, max_gap_rows=2).to_dict()

    assert summary["total_input_rows"] == 3
    assert summary["total_mixed_rows"] == 2
    assert summary["total_clusters"] == 2
    assert summary["symbol_counts"] == {"LT.NS": 1, "RELIANCE.NS": 1}


def test_cluster_review_aggregates_lifecycle_actions() -> None:
    payload = {
        "rows": [
            _mixed_row(future_lifecycle_actions=["mark_conflicted"]),
            _mixed_row(
                replay_bar_index=234,
                replay_week="2026-03-09 00:00:00",
                future_lifecycle_actions=["invalidate_qualification"],
            ),
        ]
    }

    summary = build_vsa_mixed_event_cluster_review(payload, max_gap_rows=2).to_dict()

    cluster = summary["clusters"][0]
    assert cluster["future_lifecycle_actions"] == [
        "mark_conflicted",
        "invalidate_qualification",
    ]
    assert "Lifecycle actions" in cluster["causal_read"]


def test_cluster_review_csv_renders_cluster_rows() -> None:
    summary = build_vsa_mixed_event_cluster_review({"rows": [_mixed_row()]})

    body = render_vsa_mixed_event_cluster_review_csv(summary)
    rows = list(csv.DictReader(StringIO(body)))

    assert len(rows) == 1
    assert rows[0]["cluster_id"] == "LT.NS:233-233"
    assert rows[0]["event_families"] == "effort_vs_result"
    assert rows[0]["supporting_event_codes"] == "demand_coming_in;increasing_demand"
    assert "causal_read" in rows[0]


def test_cluster_review_cli_writes_json_and_csv(tmp_path: Path) -> None:
    input_file = tmp_path / "standard_basket_causality_v2.json"
    json_output = tmp_path / "standard_basket_mixed_clusters.json"
    csv_output = tmp_path / "standard_basket_mixed_clusters.csv"
    input_file.write_text(json.dumps({"rows": [_mixed_row()]}), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/vsa_mixed_event_cluster_review.py",
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
    assert json_body["total_clusters"] == 1
    assert json_body["clusters"][0]["cluster_id"] == "LT.NS:233-233"
    assert csv_rows[0]["cluster_id"] == "LT.NS:233-233"
