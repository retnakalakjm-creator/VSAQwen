from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from vsa_absorption_background_casebook import (
    CASE_ABSORPTION_BACKGROUND_BLOCKED,
    CASE_ABSORPTION_BACKGROUND_NEEDS_FOLLOW_THROUGH,
    CASE_ABSORPTION_BACKGROUND_NONE,
    CASE_ABSORPTION_BACKGROUND_REVIEW,
    RECOMMENDED_ACTION_REVIEW,
    SEED_TYPE_ABSORPTION,
    SEED_TYPE_DIAGNOSTIC,
    build_vsa_absorption_background_casebook,
    render_vsa_absorption_background_casebook_csv,
)
from vsa_absorption_background_labels import (
    ABSORPTION_BACKGROUND_PLAIN_ENGLISH,
    AbsorptionBackgroundReviewLabel,
)


def test_absorption_casebook_marks_clean_review_from_saved_replay_rows() -> None:
    payload = {
        "results": [
            {
                "symbol": "XYZ",
                "rows": [
                    {
                        "replay_week": "2026-01-05",
                        "replay_bar_index": 10,
                        "qualification": "persistent_bearish",
                        "target_event_codes": ["increasing_supply"],
                    },
                    {
                        "replay_week": "2026-01-12",
                        "replay_bar_index": 11,
                        "qualification": "persistent_bearish",
                        "target_event_codes": ["supply_absorption"],
                        "detector_diagnostics": ["review_potential_absorption"],
                    },
                    {
                        "replay_week": "2026-01-19",
                        "replay_bar_index": 12,
                        "qualification": "persistent_bearish",
                        "target_event_codes": ["demand_coming_in"],
                    },
                ],
            }
        ]
    }

    summary = build_vsa_absorption_background_casebook(
        payload,
        lookback_rows=1,
        lookahead_rows=1,
    )

    assert summary.total_input_rows == 3
    assert summary.total_casebook_rows == 1
    assert summary.status_counts == {
        AbsorptionBackgroundReviewLabel.REVIEW.value: 1,
    }

    row = summary.rows[0]
    assert row.symbol == "XYZ"
    assert row.seed_type == SEED_TYPE_ABSORPTION
    assert row.case_type == CASE_ABSORPTION_BACKGROUND_REVIEW
    assert row.absorption_background_status == "absorption_background_review"
    assert row.review_marker == "absorption_background_review"
    assert row.frontend_label == "Absorption Background Review"
    assert row.plain_english == ABSORPTION_BACKGROUND_PLAIN_ENGLISH
    assert row.recommended_casebook_action == RECOMMENDED_ACTION_REVIEW
    assert row.prior_supply_codes == ("persistent_bearish", "increasing_supply")
    assert row.absorption_codes == ("supply_absorption",)
    assert row.follow_through_codes == ("demand_coming_in",)
    assert row.blocker_codes == ()
    assert row.diagnostic_hint_codes == ("review_potential_absorption",)
    assert row.production_safe is True
    assert "Plain English:" in row.case_read
    assert "without flipping bullish" not in row.case_read


def test_absorption_casebook_does_not_promote_diagnostic_hints() -> None:
    payload = {
        "results": [
            {
                "symbol": "XYZ",
                "rows": [
                    {
                        "replay_week": "2026-01-05",
                        "replay_bar_index": 10,
                        "qualification": "persistent_bearish",
                        "target_event_codes": ["increasing_supply"],
                    },
                    {
                        "replay_week": "2026-01-12",
                        "replay_bar_index": 11,
                        "qualification": "persistent_bearish",
                        "detector_diagnostics": ["review_potential_absorption"],
                    },
                    {
                        "replay_week": "2026-01-19",
                        "replay_bar_index": 12,
                        "qualification": "persistent_bearish",
                        "target_event_codes": ["demand_coming_in"],
                    },
                ],
            }
        ]
    }

    summary = build_vsa_absorption_background_casebook(
        payload,
        lookback_rows=1,
        lookahead_rows=1,
    )

    assert summary.total_casebook_rows == 1
    row = summary.rows[0]
    assert row.seed_type == SEED_TYPE_DIAGNOSTIC
    assert row.case_type == CASE_ABSORPTION_BACKGROUND_NONE
    assert row.absorption_background_status == "none"
    assert row.review_marker is None
    assert row.frontend_label is None
    assert row.absorption_codes == ()
    assert row.follow_through_codes == ("demand_coming_in",)
    assert row.diagnostic_hint_codes == ("review_potential_absorption",)
    assert "Diagnostic hints remain review context only" in row.audit_note or row.diagnostic_hint_codes


def test_absorption_casebook_can_ignore_diagnostic_seed_rows() -> None:
    payload = {
        "rows": [
            {
                "symbol": "XYZ",
                "replay_week": "2026-01-12",
                "replay_bar_index": 11,
                "qualification": "persistent_bearish",
                "detector_diagnostics": ["review_potential_absorption"],
            }
        ]
    }

    summary = build_vsa_absorption_background_casebook(
        payload,
        include_diagnostic_hints=False,
    )

    assert summary.total_input_rows == 1
    assert summary.total_casebook_rows == 0
    assert summary.seed_type_counts == {}


def test_absorption_casebook_needs_follow_through_when_demand_is_missing() -> None:
    payload = {
        "rows": [
            {
                "symbol": "XYZ",
                "replay_week": "2026-01-05",
                "replay_bar_index": 10,
                "qualification": "persistent_bearish",
                "target_event_codes": ["increasing_supply"],
            },
            {
                "symbol": "XYZ",
                "replay_week": "2026-01-12",
                "replay_bar_index": 11,
                "qualification": "persistent_bearish",
                "target_event_codes": ["stopping_volume"],
            },
        ]
    }

    summary = build_vsa_absorption_background_casebook(
        payload,
        lookback_rows=1,
        lookahead_rows=1,
    )

    assert summary.total_casebook_rows == 1
    row = summary.rows[0]
    assert row.case_type == CASE_ABSORPTION_BACKGROUND_NEEDS_FOLLOW_THROUGH
    assert row.absorption_background_status == "absorption_background_needs_follow_through"
    assert row.review_marker is None
    assert row.follow_through_codes == ()
    assert "needs fresh non-fallback" in row.audit_note


def test_absorption_casebook_blocks_when_supply_remains_active_on_seed_row() -> None:
    payload = {
        "rows": [
            {
                "symbol": "XYZ",
                "replay_week": "2026-01-05",
                "replay_bar_index": 10,
                "qualification": "persistent_bearish",
                "target_event_codes": ["increasing_supply"],
            },
            {
                "symbol": "XYZ",
                "replay_week": "2026-01-12",
                "replay_bar_index": 11,
                "qualification": "persistent_bearish",
                "target_event_codes": ["supply_absorption", "hidden_supply"],
            },
            {
                "symbol": "XYZ",
                "replay_week": "2026-01-19",
                "replay_bar_index": 12,
                "qualification": "persistent_bearish",
                "target_event_codes": ["increasing_demand"],
            },
        ]
    }

    summary = build_vsa_absorption_background_casebook(
        payload,
        lookback_rows=1,
        lookahead_rows=1,
    )

    assert summary.total_casebook_rows == 1
    row = summary.rows[0]
    assert row.case_type == CASE_ABSORPTION_BACKGROUND_BLOCKED
    assert row.absorption_background_status == "absorption_background_blocked"
    assert row.review_marker is None
    assert row.absorption_codes == ("supply_absorption",)
    assert row.follow_through_codes == ("increasing_demand",)
    assert row.blocker_codes == ("hidden_supply",)
    assert "blocked by same-window" in row.audit_note


def test_absorption_casebook_serializes_to_json_ready_dict_and_csv() -> None:
    summary = build_vsa_absorption_background_casebook(
        [
            {
                "symbol": "XYZ",
                "replay_week": "2026-01-05",
                "replay_bar_index": 10,
                "qualification": "persistent_bearish",
                "target_event_codes": ["increasing_supply"],
            },
            {
                "symbol": "XYZ",
                "replay_week": "2026-01-12",
                "replay_bar_index": 11,
                "qualification": "persistent_bearish",
                "target_event_codes": ["supply_absorption"],
            },
            {
                "symbol": "XYZ",
                "replay_week": "2026-01-19",
                "replay_bar_index": 12,
                "qualification": "persistent_bearish",
                "target_event_codes": ["demand_coming_in"],
            },
        ],
        lookback_rows=1,
        lookahead_rows=1,
    )

    payload = summary.to_dict()
    assert payload["audit_only"] is True
    assert payload["production_safe"] is True
    assert payload["total_casebook_rows"] == 1
    assert payload["rows"][0]["plain_english"] == ABSORPTION_BACKGROUND_PLAIN_ENGLISH
    assert payload["top_casebook_items"][0]["plain_english"] == ABSORPTION_BACKGROUND_PLAIN_ENGLISH

    csv_text = render_vsa_absorption_background_casebook_csv(summary)
    assert "casebook_id,symbol,seed_type" in csv_text
    assert "Absorption Background Review" in csv_text
    assert "Selling pressure may be getting absorbed" in csv_text


def test_absorption_casebook_cli_runs_from_repo_root(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    input_path = tmp_path / "input.json"
    json_output = tmp_path / "casebook.json"
    csv_output = tmp_path / "casebook.csv"
    input_path.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "symbol": "XYZ",
                        "rows": [
                            {
                                "replay_week": "2026-01-05",
                                "replay_bar_index": 10,
                                "qualification": "persistent_bearish",
                                "target_event_codes": ["increasing_supply"],
                            },
                            {
                                "replay_week": "2026-01-12",
                                "replay_bar_index": 11,
                                "qualification": "persistent_bearish",
                                "target_event_codes": ["supply_absorption"],
                            },
                            {
                                "replay_week": "2026-01-19",
                                "replay_bar_index": 12,
                                "qualification": "persistent_bearish",
                                "target_event_codes": ["demand_coming_in"],
                            },
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            sys.executable,
            "scripts/vsa_absorption_background_casebook.py",
            str(input_path),
            "--json-output",
            str(json_output),
            "--csv-output",
            str(csv_output),
            "--lookback-rows",
            "1",
            "--lookahead-rows",
            "1",
        ],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )

    output_payload = json.loads(json_output.read_text(encoding="utf-8"))
    assert output_payload["total_casebook_rows"] == 1
    assert output_payload["rows"][0]["review_marker"] == "absorption_background_review"
    assert "absorption_background_review" in csv_output.read_text(encoding="utf-8")
