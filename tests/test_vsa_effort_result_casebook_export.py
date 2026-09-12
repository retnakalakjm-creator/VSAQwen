from __future__ import annotations

import json

import pandas as pd
import pytest

from audit.export_effort_result_casebook import (
    build_effort_result_casebook,
    render_casebook_markdown,
    write_casebook_csv,
)


def _event_payload(*codes: str) -> str:
    return json.dumps([{"code": code} for code in codes])


def _rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for symbol, offset in (("LT.NS", 0.0), ("RELIANCE.NS", 100.0)):
        closes = [
            100.0 + offset,
            103.0 + offset,
            99.0 + offset,
            97.0 + offset,
            101.0 + offset,
        ]
        for bar_index, close in enumerate(closes):
            if bar_index in {0, 2}:
                volume_ratio = 0.5
                spread_ratio = 1.6
                existing_events = "[]"
            elif bar_index == 1:
                volume_ratio = 2.0
                spread_ratio = 2.0
                existing_events = _event_payload("EvidenceCode.SUPPLY_COMING_IN")
            else:
                volume_ratio = 1.0
                spread_ratio = 1.0
                existing_events = "[]"
            rows.append(
                {
                    "symbol": symbol,
                    "bar_index": bar_index,
                    "week_beginning": f"2026-01-{bar_index + 1:02d}",
                    "close": close,
                    "volume_ratio": volume_ratio,
                    "spread_ratio": spread_ratio,
                    "existing_events": existing_events,
                }
            )
    return rows


def _csv(path, rows: list[dict[str, object]]) -> None:
    pd.DataFrame(rows).to_csv(path, index=False)


def test_casebook_exports_targeted_effort_result_examples(tmp_path) -> None:
    path = tmp_path / "historical_effort_result_validation.csv"
    _csv(path, _rows())

    report = build_effort_result_casebook(
        path,
        targets=("RESULT_GT_EFFORT", "EFFORT_RESULT+SUPPLY_COMING_IN"),
        horizons=(1, 2),
        max_examples_per_target=10,
    )

    casebooks = {row["target"]: row for row in report["casebooks"]}

    assert report["report_type"] == "effort_result_casebook"
    assert report["report_schema_version"] == 1
    assert report["audit_only"] is True
    assert report["may_change_scoring"] is False
    assert report["may_change_ranking"] is False
    assert report["may_change_actionability"] is False
    assert report["may_activate_detector"] is False
    assert report["requires_manual_case_review"] is True
    assert report["requires_separate_production_pr"] is True
    assert casebooks["RESULT_GT_EFFORT"]["matched_bars"] == 4
    assert casebooks["EFFORT_RESULT+SUPPLY_COMING_IN"]["matched_bars"] == 2
    assert (
        casebooks["RESULT_GT_EFFORT"]["examples"][0][
            "effort_result_candidate"
        ]
        == "RESULT_GT_EFFORT"
    )
    assert "forward_return_1" in casebooks["RESULT_GT_EFFORT"]["examples"][0]
    assert (
        "SUPPLY_COMING_IN"
        in casebooks["EFFORT_RESULT+SUPPLY_COMING_IN"]["examples"][0]["events"]
    )


def test_casebook_respects_per_target_limit(tmp_path) -> None:
    path = tmp_path / "historical_effort_result_validation.csv"
    _csv(path, _rows())

    report = build_effort_result_casebook(
        path,
        targets=("RESULT_GT_EFFORT", "EFFORT_RESULT+SUPPLY_COMING_IN"),
        max_examples_per_target=1,
    )

    assert [casebook["exported_examples"] for casebook in report["casebooks"]] == [1, 1]
    assert report["total_matched_bars"] == 6


def test_casebook_renders_markdown_and_csv(tmp_path) -> None:
    path = tmp_path / "historical_effort_result_validation.csv"
    output = tmp_path / "casebook.csv"
    _csv(path, _rows())

    report = build_effort_result_casebook(
        path,
        targets=("RESULT_GT_EFFORT", "EFFORT_RESULT+SUPPLY_COMING_IN"),
        horizons=(1, 2),
        max_examples_per_target=2,
    )
    markdown = render_casebook_markdown(report)
    write_casebook_csv(report, output)

    assert "# Effort/Result Casebook" in markdown
    assert "RESULT_GT_EFFORT" in markdown
    assert "EFFORT_RESULT+SUPPLY_COMING_IN" in markdown
    assert "May change scoring: false" in markdown
    csv_rows = pd.read_csv(output)
    assert set(csv_rows["target"]) == {
        "RESULT_GT_EFFORT",
        "EFFORT_RESULT+SUPPLY_COMING_IN",
    }


def test_casebook_validates_inputs_before_export(tmp_path) -> None:
    path = tmp_path / "bad.csv"
    pd.DataFrame([{"symbol": "LT.NS"}]).to_csv(path, index=False)

    with pytest.raises(ValueError, match="Missing required columns"):
        build_effort_result_casebook(path)

    good = tmp_path / "good.csv"
    _csv(good, _rows())

    with pytest.raises(ValueError, match="max_examples_per_target"):
        build_effort_result_casebook(good, max_examples_per_target=0)

    with pytest.raises(ValueError, match="at least one target"):
        build_effort_result_casebook(good, targets=())
