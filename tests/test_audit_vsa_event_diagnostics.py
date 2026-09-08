from __future__ import annotations

import pandas as pd

from audit.vsa_event_diagnostics import (
    build_vsa_event_diagnostic_tables,
    explode_vsa_event_rows,
    summarize_vsa_event_outcomes,
    summarize_vsa_event_stability,
    write_vsa_event_diagnostic_bundle,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _row(
                "AAA",
                "stopping_volume|unknown_code",
                "stopping_volume",
                "long",
                1,
                0.05,
            ),
            _row("BBB", "stopping_volume", "", "long", 1, 0.03),
            _row("CCC", "upthrust", "", "short", 1, -0.04),
            _row("DDD", "upthrust", "", "short", 1, -0.02),
            _row(
                "EEE",
                "no_supply",
                "test",
                "long",
                2,
                0.01,
                complete=False,
            ),
            _row(
                "FFF",
                "shakeout",
                "",
                "long",
                2,
                None,
                outcome_available=False,
            ),
        ]
    )


def _row(
    symbol: str,
    scoring_evidence: str,
    target_evidence: str,
    side: str,
    horizon: int,
    favorable_return: float | None,
    *,
    outcome_available: bool = True,
    complete: bool = True,
) -> dict[str, object]:
    raw_return = favorable_return if side == "long" else (
        None if favorable_return is None else -favorable_return
    )
    return {
        "symbol": symbol,
        "candidate_id": f"{symbol}-{horizon}",
        "horizon_bars": horizon,
        "outcome_available": outcome_available,
        "complete": complete,
        "actionable": True,
        "signal_bar_anomaly": False,
        "qualification": "persistent_bullish" if side == "long" else "persistent_bearish",
        "side": side,
        "target_bar_evidence_codes": target_evidence,
        "qualifying_evidence_codes": "",
        "scoring_evidence_codes": scoring_evidence,
        "campaign_evidence_codes": "",
        "raw_return": raw_return,
        "favorable_return": favorable_return,
        "mfe": 0.06 if favorable_return is not None else None,
        "mae": -0.02 if favorable_return is not None else None,
    }


def test_explode_vsa_event_rows_normalizes_and_deduplicates_codes() -> None:
    exploded = explode_vsa_event_rows(_frame())

    first_row_codes = exploded[exploded["symbol"] == "AAA"]["vsa_event_code"].tolist()
    assert first_row_codes == ["STOPPING_VOLUME"]
    assert "UNKNOWN_CODE" not in set(exploded["vsa_event_code"])
    assert set(exploded["vsa_event_code"]) >= {
        "STOPPING_VOLUME",
        "UPTHRUST",
        "NO_SUPPLY",
        "TEST",
        "SHAKEOUT",
    }


def test_summarize_vsa_event_outcomes_filters_completed_rows() -> None:
    summary = summarize_vsa_event_outcomes(_frame(), min_samples=2)

    assert list(summary["vsa_event_code"]) == ["STOPPING_VOLUME", "UPTHRUST"]
    assert set(summary["sample_count"]) == {2}
    assert "module" in summary.columns
    assert "recognition_timing" in summary.columns
    assert "NO_SUPPLY" not in set(summary["vsa_event_code"])
    assert "SHAKEOUT" not in set(summary["vsa_event_code"])


def test_summarize_vsa_event_stability_adds_contract_metadata() -> None:
    stability = summarize_vsa_event_stability(_frame(), min_samples=2)

    assert set(stability["vsa_event_code"]) == {"STOPPING_VOLUME", "UPTHRUST"}
    assert "stability_grade" in stability.columns
    assert stability["sample_count"].min() == 2
    assert stability["module"].notna().all()


def test_build_vsa_event_diagnostic_tables_returns_bundle() -> None:
    tables = build_vsa_event_diagnostic_tables(
        _frame(),
        min_samples=2,
        stability_min_samples=2,
    )

    assert set(tables) == {
        "vsa_event_summary",
        "vsa_event_stability",
        "vsa_event_contracts",
    }
    assert "ABSORPTION" in set(tables["vsa_event_contracts"]["evidence_code"])
    assert "source_documents" in tables["vsa_event_contracts"].columns


def test_write_vsa_event_diagnostic_bundle_writes_csv_files(tmp_path) -> None:
    paths = write_vsa_event_diagnostic_bundle(
        _frame(),
        tmp_path / "vsa",
        min_samples=2,
        stability_min_samples=2,
    )

    assert paths.output_dir.exists()
    assert paths.event_summary.exists()
    assert paths.event_stability.exists()
    assert paths.event_contracts.exists()
    assert paths.metadata.exists()

    summary = pd.read_csv(paths.event_summary)
    stability = pd.read_csv(paths.event_stability)
    contracts = pd.read_csv(paths.event_contracts)
    metadata = pd.read_csv(paths.metadata)
    metadata_values = dict(zip(metadata["metric"], metadata["value"], strict=True))

    assert set(summary["vsa_event_code"]) == {"STOPPING_VOLUME", "UPTHRUST"}
    assert set(stability["vsa_event_code"]) == {"STOPPING_VOLUME", "UPTHRUST"}
    assert "ABSORPTION" in set(contracts["evidence_code"])
    assert int(metadata_values["source_rows"]) == 6
    assert int(metadata_values["vsa_event_summary_rows"]) == len(summary)
    assert int(metadata_values["vsa_event_stability_rows"]) == len(stability)
    assert int(metadata_values["stability_min_samples"]) == 2


def test_vsa_event_diagnostic_arguments_are_validated(tmp_path) -> None:
    frame = _frame()

    try:
        summarize_vsa_event_outcomes(frame, min_samples=0)
    except ValueError as exc:
        assert "min_samples" in str(exc)
    else:
        raise AssertionError("min_samples=0 should fail")

    try:
        summarize_vsa_event_stability(frame, min_samples=0)
    except ValueError as exc:
        assert "min_samples" in str(exc)
    else:
        raise AssertionError("stability min_samples=0 should fail")

    try:
        write_vsa_event_diagnostic_bundle(
            frame,
            tmp_path,
            stability_z_score=0.0,
        )
    except ValueError as exc:
        assert "stability_z_score" in str(exc)
    else:
        raise AssertionError("stability_z_score=0 should fail")

    try:
        explode_vsa_event_rows(pd.DataFrame({"other": []}))
    except ValueError as exc:
        assert "Missing VSA evidence code columns" in str(exc)
    else:
        raise AssertionError("missing evidence columns should fail")
