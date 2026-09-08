from __future__ import annotations

import pandas as pd

from audit.reports import (
    build_calibration_report_tables,
    write_calibration_report_bundle,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _row("AAA", "stopping_volume", "persistent_bullish", "long", 1, 0.05),
            _row("BBB", "stopping_volume", "persistent_bullish", "long", 1, 0.03),
            _row("CCC", "upthrust", "persistent_bearish", "short", 1, -0.04),
            _row("DDD", "upthrust", "persistent_bearish", "short", 1, -0.02),
            _row("EEE", "no_supply|test", "persistent_bullish", "long", 2, 0.01),
            _row("FFF", "no_supply|test", "persistent_bullish", "long", 2, 0.02),
            _row("GGG", "ignored_latest", "persistent_bullish", "long", 1, None, outcome_available=False),
            _row("HHH", "ignored_partial", "persistent_bullish", "long", 1, 0.08, complete=False),
        ]
    )


def _row(
    symbol: str,
    evidence: str,
    qualification: str,
    side: str,
    horizon: int,
    favorable_return: float | None,
    *,
    outcome_available: bool = True,
    complete: bool = True,
) -> dict[str, object]:
    raw_return = favorable_return if side == "long" else (None if favorable_return is None else -favorable_return)
    return {
        "symbol": symbol,
        "candidate_id": 1,
        "horizon_bars": horizon,
        "outcome_available": outcome_available,
        "complete": complete,
        "actionable": True,
        "signal_bar_anomaly": False,
        "qualification": qualification,
        "side": side,
        "scoring_evidence_codes": evidence,
        "raw_return": raw_return,
        "favorable_return": favorable_return,
        "mfe": 0.06 if favorable_return is not None else None,
        "mae": -0.02 if favorable_return is not None else None,
    }


def test_build_calibration_report_tables_returns_standard_bundle() -> None:
    tables = build_calibration_report_tables(
        _frame(),
        min_samples=2,
        top_n=2,
    )

    assert set(tables) == {
        "evidence_summary",
        "qualification_summary",
        "top_positive_evidence",
        "bottom_negative_evidence",
    }
    assert list(tables["top_positive_evidence"]["group_key"])[0] == "stopping_volume|1|long"
    assert list(tables["bottom_negative_evidence"]["group_key"])[0] == "upthrust|1|short"
    assert len(tables["top_positive_evidence"]) == 2
    assert "ignored_latest" not in "|".join(tables["evidence_summary"]["group_key"].astype(str))
    assert "ignored_partial" not in "|".join(tables["evidence_summary"]["group_key"].astype(str))


def test_write_calibration_report_bundle_writes_csv_files(tmp_path) -> None:
    paths = write_calibration_report_bundle(
        _frame(),
        tmp_path / "reports",
        min_samples=2,
        top_n=3,
    )

    assert paths.output_dir.exists()
    assert paths.evidence_summary.exists()
    assert paths.qualification_summary.exists()
    assert paths.top_positive_evidence.exists()
    assert paths.bottom_negative_evidence.exists()
    assert paths.metadata.exists()

    evidence = pd.read_csv(paths.evidence_summary)
    top_positive = pd.read_csv(paths.top_positive_evidence)
    bottom_negative = pd.read_csv(paths.bottom_negative_evidence)
    metadata = pd.read_csv(paths.metadata)
    metadata_values = dict(zip(metadata["metric"], metadata["value"], strict=True))

    assert evidence["sample_count"].min() >= 2
    assert top_positive.loc[0, "group_key"] == "stopping_volume|1|long"
    assert bottom_negative.loc[0, "group_key"] == "upthrust|1|short"
    assert int(metadata_values["source_rows"]) == 8
    assert int(metadata_values["evidence_summary_rows"]) == len(evidence)


def test_report_arguments_are_validated(tmp_path) -> None:
    frame = _frame()

    try:
        build_calibration_report_tables(frame, min_samples=0)
    except ValueError as exc:
        assert "min_samples" in str(exc)
    else:
        raise AssertionError("min_samples=0 should fail")

    try:
        write_calibration_report_bundle(frame, tmp_path, top_n=0)
    except ValueError as exc:
        assert "top_n" in str(exc)
    else:
        raise AssertionError("top_n=0 should fail")
