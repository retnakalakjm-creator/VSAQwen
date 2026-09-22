from __future__ import annotations

import json

import pandas as pd

from scripts.audit_causal_vsa_scanner_replay import (
    COMPARE_SUMMARY_NAME,
    DELTA_NAME,
    LEDGER_NAME,
    SUMMARY_NAME,
    compare,
)


def _row(
    *,
    scoring_codes: str = "no_supply",
    scoring_bar_index: int = 10,
    actionable: bool = False,
) -> dict[str, object]:
    return {
        "symbol": "TEST.NS",
        "bar_index": 12,
        "week": "2026-01-09",
        "qualification": "persistent_bullish",
        "qualification_actionable": True,
        "actionable": actionable,
        "reason": "reason",
        "target_codes": "",
        "scoring_codes": scoring_codes,
        "qualifying_codes": "structural_progression_improving",
        "scoring_bar_index": scoring_bar_index,
        "scoring_evidence_age": 12 - scoring_bar_index,
        "used_fallback_evidence": scoring_bar_index != 12,
        "confidence": 0.5,
        "net_strength": 0.2,
        "net_pressure": 0.1,
        "ranking_score": 0.2,
    }


def _write_capture(directory, row: dict[str, object]) -> None:
    directory.mkdir(parents=True)
    pd.DataFrame([row]).to_csv(directory / LEDGER_NAME, index=False)
    (directory / SUMMARY_NAME).write_text(
        json.dumps(
            {
                "input_snapshot_manifest_sha256": "a" * 64,
            }
        ),
        encoding="utf-8",
    )


def test_compare_reports_scoring_and_actionability_deltas(tmp_path) -> None:
    before = tmp_path / "before"
    after = tmp_path / "after"
    output = tmp_path / "compare"

    _write_capture(before, _row())
    _write_capture(
        after,
        _row(
            scoring_codes="demand_coming_in",
            scoring_bar_index=11,
            actionable=True,
        ),
    )

    summary = compare(before, after, output)

    assert summary["same_input_manifest"] is True
    assert summary["changed_candidate_row_count"] == 1
    assert summary["target_code_change_count"] == 0
    assert summary["qualifying_code_change_count"] == 0
    assert summary["scoring_code_change_count"] == 1
    assert summary["scoring_bar_change_count"] == 1
    assert summary["scoring_age_change_count"] == 1
    assert summary["actionable_change_count"] == 1
    assert (output / DELTA_NAME).exists()
    assert (output / COMPARE_SUMMARY_NAME).exists()
