from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd

from audit.weekly_authority_audit import (
    WEEKLY_AUTHORITY_AUDIT_ID,
    build_weekly_authority_audit,
    write_weekly_authority_audit,
)
from background.qualification import PatternQualification


def _daily(periods: int = 80) -> pd.DataFrame:
    index = pd.bdate_range("2026-05-04", periods=periods)
    values = [100.0 + index * 0.5 for index in range(periods)]
    return pd.DataFrame(
        {
            "open": values,
            "high": [value + 2.0 for value in values],
            "low": [value - 1.0 for value in values],
            "close": [value + 1.0 for value in values],
            "volume": [1000.0 + index * 10.0 for index in range(periods)],
        },
        index=index,
    )


def _candidate(
    *,
    week: str,
    qualification: PatternQualification,
):
    return SimpleNamespace(
        actionable=True,
        qualification=qualification,
        week=week,
        confidence=0.82,
        net_strength=1.1,
        net_pressure=0.7,
        qualifying_evidence=(),
        scoring_evidence=(),
    )


class _FakeMetrics:
    def calculate(self, frame: pd.DataFrame) -> pd.DataFrame:
        return frame.copy()


class _FakeRunner:
    def __init__(self, candidates):
        self._candidates = list(candidates)

    def scan(self, metrics: pd.DataFrame):
        assert not metrics.empty
        return list(self._candidates)


def test_audit_separates_setup_direction_from_selected_daily_authority() -> None:
    audit = build_weekly_authority_audit(
        symbol="lt.ns",
        daily=_daily(),
        now="2026-09-18T16:00:00+05:30",
        historical_runner=_FakeRunner(
            (
                _candidate(
                    week="2026-05-04",
                    qualification=PatternQualification.PERSISTENT_BULLISH,
                ),
                _candidate(
                    week="2026-06-01",
                    qualification=PatternQualification.PERSISTENT_BEARISH,
                ),
            )
        ),
        metrics_engine=_FakeMetrics(),
    )

    assert audit.symbol == "LT.NS"
    assert audit.audit_id == WEEKLY_AUTHORITY_AUDIT_ID
    assert audit.setup_count == 2
    assert audit.bullish_setup_count == 1
    assert audit.bearish_setup_count == 1
    assert audit.assignment_count > 0
    assert audit.bullish_assignment_count > 0
    assert audit.bearish_assignment_count > 0
    assert audit.selected_setup_count == 2
    assert audit.unselected_setup_count == 0
    assert audit.is_actionable is False


def test_audit_ledger_preserves_causal_availability_and_selection_span() -> None:
    audit = build_weekly_authority_audit(
        symbol="LT.NS",
        daily=_daily(),
        now="2026-09-18T16:00:00+05:30",
        historical_runner=_FakeRunner(
            (
                _candidate(
                    week="2026-05-04",
                    qualification=PatternQualification.PERSISTENT_BULLISH,
                ),
                _candidate(
                    week="2026-06-01",
                    qualification=PatternQualification.PERSISTENT_BEARISH,
                ),
            )
        ),
        metrics_engine=_FakeMetrics(),
    )

    first, second = audit.rows
    assert first.available_session > first.completion_session
    assert second.available_session > second.completion_session
    assert first.first_selected_session == first.available_session
    assert second.first_selected_session == second.available_session
    assert first.last_selected_session < second.first_selected_session
    assert first.selected_daily_count > 0
    assert second.selected_daily_count > 0


def test_all_bearish_setup_history_remains_all_bearish_in_audit() -> None:
    audit = build_weekly_authority_audit(
        symbol="LT.NS",
        daily=_daily(),
        now="2026-09-18T16:00:00+05:30",
        historical_runner=_FakeRunner(
            (
                _candidate(
                    week="2026-05-04",
                    qualification=PatternQualification.PERSISTENT_BEARISH,
                ),
                _candidate(
                    week="2026-06-01",
                    qualification=PatternQualification.PERSISTENT_BEARISH,
                ),
            )
        ),
        metrics_engine=_FakeMetrics(),
    )

    assert audit.bullish_setup_count == 0
    assert audit.bearish_setup_count == 2
    assert audit.bullish_assignment_count == 0
    assert audit.bearish_assignment_count == audit.assignment_count


def test_audit_outputs_summary_and_setup_ledger(tmp_path) -> None:
    audit = build_weekly_authority_audit(
        symbol="LT.NS",
        daily=_daily(),
        now="2026-09-18T16:00:00+05:30",
        historical_runner=_FakeRunner(
            (
                _candidate(
                    week="2026-05-04",
                    qualification=PatternQualification.PERSISTENT_BULLISH,
                ),
            )
        ),
        metrics_engine=_FakeMetrics(),
    )

    paths = write_weekly_authority_audit(audit, tmp_path)
    summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    ledger = pd.read_csv(paths.setup_ledger_csv)

    assert summary["setup_count"] == 1
    assert summary["assignment_count"] == audit.assignment_count
    assert summary["is_actionable"] is False
    assert len(ledger) == 1
    assert ledger.loc[0, "direction"] == "bullish"
    assert ledger.loc[0, "selected_daily_count"] > 0
