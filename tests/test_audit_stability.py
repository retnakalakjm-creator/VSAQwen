from __future__ import annotations

import pandas as pd

from audit.stability import (
    add_stability_labels,
    summarize_evidence_stability,
    summarize_return_stability,
    wilson_interval,
)


def _frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    rows.extend(_rows("AAA.NS", "stopping_volume", "long", [0.04, 0.03, 0.02, 0.01]))
    rows.extend(_rows("BBB.NS", "stopping_volume", "long", [0.05, 0.04, 0.03, 0.02]))
    rows.extend(_rows("CCC.NS", "upthrust", "short", [-0.04, -0.03, -0.02, -0.01]))
    rows.extend(_rows("DDD.NS", "upthrust", "short", [-0.05, -0.04, -0.03, -0.02]))
    rows.append(
        _row(
            "EEE.NS",
            "ignored_partial",
            "long",
            0.50,
            outcome_available=True,
            complete=False,
        )
    )
    rows.append(
        _row(
            "FFF.NS",
            "ignored_latest",
            "long",
            None,
            outcome_available=False,
            complete=False,
        )
    )
    return pd.DataFrame(rows)


def _rows(symbol: str, evidence: str, side: str, values: list[float]) -> list[dict[str, object]]:
    return [_row(symbol, evidence, side, value) for value in values]


def _row(
    symbol: str,
    evidence: str,
    side: str,
    favorable_return: float | None,
    *,
    outcome_available: bool = True,
    complete: bool = True,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "horizon_bars": 1,
        "side": side,
        "outcome_available": outcome_available,
        "complete": complete,
        "scoring_evidence_codes": evidence,
        "qualification": "persistent_bullish" if side == "long" else "persistent_bearish",
        "favorable_return": favorable_return,
    }


def test_wilson_interval_bounds_are_valid() -> None:
    low, high = wilson_interval(7, 10)

    assert 0.0 <= low <= high <= 1.0
    assert low < 0.7 < high


def test_wilson_interval_validates_inputs() -> None:
    try:
        wilson_interval(2, 1)
    except ValueError as exc:
        assert "successes" in str(exc)
    else:
        raise AssertionError("successes greater than total should fail")

    try:
        wilson_interval(-1, 10)
    except ValueError as exc:
        assert "successes" in str(exc)
    else:
        raise AssertionError("negative successes should fail")


def test_summarize_return_stability_groups_completed_rows() -> None:
    summary = summarize_return_stability(
        _frame(),
        group_by=("scoring_evidence_codes", "horizon_bars", "side"),
        min_samples=2,
    )

    assert set(summary["group_key"]) == {
        "stopping_volume|1|long",
        "upthrust|1|short",
    }
    positive = summary[summary["group_key"] == "stopping_volume|1|long"].iloc[0]
    negative = summary[summary["group_key"] == "upthrust|1|short"].iloc[0]

    assert positive["sample_count"] == 8
    assert positive["symbol_count"] == 2
    assert positive["positive_count"] == 8
    assert positive["negative_count"] == 0
    assert positive["win_rate"] == 1.0
    assert positive["avg_favorable_return"] > 0.0
    assert positive["favorable_return_ci_low"] > 0.0

    assert negative["sample_count"] == 8
    assert negative["positive_count"] == 0
    assert negative["negative_count"] == 8
    assert negative["win_rate"] == 0.0
    assert negative["avg_favorable_return"] < 0.0
    assert negative["favorable_return_ci_high"] < 0.0

    assert "ignored_partial" not in "|".join(summary["group_key"].astype(str))
    assert "ignored_latest" not in "|".join(summary["group_key"].astype(str))


def test_summarize_evidence_stability_explodes_codes() -> None:
    frame = pd.DataFrame(
        [
            _row("AAA.NS", "no_supply|test", "long", 0.03),
            _row("BBB.NS", "no_supply|test", "long", 0.01),
        ]
    )

    summary = summarize_evidence_stability(frame, min_samples=2)

    assert set(summary["group_key"]) == {
        "no_supply|1|long",
        "test|1|long",
    }
    assert set(summary["sample_count"]) == {2}


def test_add_stability_labels_marks_insufficient_and_directional_rows() -> None:
    summary = pd.DataFrame(
        [
            {
                "sample_count": 1,
                "win_rate": 1.0,
                "win_rate_ci_low": 0.2,
                "win_rate_ci_high": 1.0,
                "avg_favorable_return": 0.05,
                "favorable_return_ci_low": 0.04,
                "favorable_return_ci_high": 0.06,
            },
            {
                "sample_count": 50,
                "win_rate": 0.60,
                "win_rate_ci_low": 0.52,
                "win_rate_ci_high": 0.70,
                "avg_favorable_return": 0.02,
                "favorable_return_ci_low": 0.01,
                "favorable_return_ci_high": 0.03,
            },
            {
                "sample_count": 50,
                "win_rate": 0.40,
                "win_rate_ci_low": 0.30,
                "win_rate_ci_high": 0.48,
                "avg_favorable_return": -0.02,
                "favorable_return_ci_low": -0.03,
                "favorable_return_ci_high": -0.01,
            },
        ]
    )

    labelled = add_stability_labels(summary, min_samples=30)

    assert list(labelled["stability_grade"]) == [
        "insufficient_sample",
        "stable_positive",
        "stable_negative",
    ]


def test_stability_validation_errors_are_clear() -> None:
    frame = _frame()

    try:
        summarize_return_stability(frame, group_by=[], min_samples=1)
    except ValueError as exc:
        assert "group_by" in str(exc)
    else:
        raise AssertionError("empty group_by should fail")

    try:
        summarize_return_stability(frame, group_by="side", min_samples=0)
    except ValueError as exc:
        assert "min_samples" in str(exc)
    else:
        raise AssertionError("min_samples=0 should fail")

    try:
        summarize_return_stability(frame.drop(columns=["complete"]), group_by="side")
    except ValueError as exc:
        assert "Missing required stability columns" in str(exc)
    else:
        raise AssertionError("missing columns should fail")
