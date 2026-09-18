from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd

from audit.genuine_daily_sequence_case import (
    ProductionWeeklySourceFingerprint,
)
from audit.weekly_candidate_decision_audit import (
    WEEKLY_CANDIDATE_DECISION_AUDIT_ID,
    audit_weekly_candidate_decisions,
    build_weekly_candidate_decision_audit,
    write_weekly_candidate_decision_audit,
)
from background.qualification import (
    PatternQualification,
    PatternQualificationResult,
)


def _fingerprint() -> ProductionWeeklySourceFingerprint:
    return ProductionWeeklySourceFingerprint(
        symbol="LT.NS",
        row_count=10,
        first_week="2026-01-02T00:00:00",
        last_week="2026-03-06T00:00:00",
        sha256="sha256:test-weekly",
    )


def _candidate(
    *,
    week: str,
    qualification: PatternQualification,
    qualification_actionable: bool,
    confidence: float = 0.8,
    reason: str = "test reason",
    anomaly: bool = False,
):
    return SimpleNamespace(
        bar_index=20,
        week=week,
        qualification=qualification,
        qualification_result=PatternQualificationResult(
            qualification=qualification,
            is_actionable_evidence=qualification_actionable,
            reason=reason,
        ),
        actionable=qualification_actionable and confidence > 0 and not anomaly,
        confidence=confidence,
        net_strength=0.7,
        net_pressure=-0.5,
        scoring_bar_index=20,
        scoring_evidence_age=0,
        used_fallback_evidence=False,
        signal_bar_anomaly=anomaly,
        reason=reason,
        qualifying_evidence_codes=(),
        scoring_evidence_codes=(),
        qualifying_evidence=(),
        scoring_evidence=(),
    )


def test_audit_separates_qualification_actionability_and_materialization() -> None:
    candidates = (
        _candidate(
            week="2026-01-05",
            qualification=PatternQualification.UNQUALIFIED,
            qualification_actionable=False,
            reason="unqualified",
        ),
        _candidate(
            week="2026-01-12",
            qualification=PatternQualification.PERSISTENT_BULLISH,
            qualification_actionable=False,
            reason="bullish missing confirmation",
        ),
        _candidate(
            week="2026-01-19",
            qualification=PatternQualification.PERSISTENT_BULLISH,
            qualification_actionable=True,
            reason="bullish confirmed",
        ),
        _candidate(
            week="2026-01-26",
            qualification=PatternQualification.PERSISTENT_BEARISH,
            qualification_actionable=True,
            reason="bearish confirmed",
        ),
    )

    audit = audit_weekly_candidate_decisions(
        symbol="lt.ns",
        candidates=candidates,
        source_fingerprint=_fingerprint(),
    )

    assert audit.symbol == "LT.NS"
    assert audit.audit_id == WEEKLY_CANDIDATE_DECISION_AUDIT_ID
    assert audit.candidate_count == 4
    assert audit.qualification_counts == {
        "persistent_bearish": 1,
        "persistent_bullish": 2,
        "unqualified": 1,
    }
    assert audit.actionable_counts == {
        "unqualified": 0,
        "persistent_bullish": 1,
        "persistent_bearish": 1,
    }
    assert audit.materialized_direction_counts == {
        "bearish": 1,
        "bullish": 1,
    }
    assert audit.materialized_setup_count == 2
    assert audit.is_actionable is False


def test_audit_preserves_exact_reason_counts_by_persistent_direction() -> None:
    audit = audit_weekly_candidate_decisions(
        symbol="LT.NS",
        candidates=(
            _candidate(
                week="2026-01-05",
                qualification=PatternQualification.PERSISTENT_BULLISH,
                qualification_actionable=False,
                reason="missing bullish VSA",
            ),
            _candidate(
                week="2026-01-12",
                qualification=PatternQualification.PERSISTENT_BULLISH,
                qualification_actionable=False,
                reason="missing bullish VSA",
            ),
            _candidate(
                week="2026-01-19",
                qualification=PatternQualification.PERSISTENT_BEARISH,
                qualification_actionable=True,
                reason="bearish confirmed",
            ),
        ),
        source_fingerprint=_fingerprint(),
    )

    assert audit.persistent_bullish_reason_counts == {
        "missing bullish VSA": 2
    }
    assert audit.persistent_bearish_reason_counts == {
        "bearish confirmed": 1
    }


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


class _FakeMetrics:
    def calculate(self, frame: pd.DataFrame) -> pd.DataFrame:
        return frame.copy()


class _FakeRunner:
    def scan(self, metrics: pd.DataFrame):
        assert not metrics.empty
        return [
            _candidate(
                week="2026-06-01",
                qualification=PatternQualification.PERSISTENT_BEARISH,
                qualification_actionable=True,
                reason="bearish confirmed",
            )
        ]


def test_build_audit_uses_completed_weekly_source_fingerprint() -> None:
    audit = build_weekly_candidate_decision_audit(
        symbol="LT.NS",
        daily=_daily(),
        now="2026-09-18T16:00:00+05:30",
        historical_runner=_FakeRunner(),
        metrics_engine=_FakeMetrics(),
    )

    assert audit.candidate_count == 1
    assert audit.materialized_setup_count == 1
    assert audit.source_fingerprint.sha256.startswith("sha256:")
    assert audit.source_fingerprint.symbol == "LT.NS"


def test_writer_outputs_summary_and_candidate_ledger(tmp_path) -> None:
    audit = audit_weekly_candidate_decisions(
        symbol="LT.NS",
        candidates=(
            _candidate(
                week="2026-01-19",
                qualification=PatternQualification.PERSISTENT_BEARISH,
                qualification_actionable=True,
                reason="bearish confirmed",
            ),
        ),
        source_fingerprint=_fingerprint(),
    )

    paths = write_weekly_candidate_decision_audit(audit, tmp_path)
    summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    ledger = pd.read_csv(paths.candidate_ledger_csv)

    assert summary["candidate_count"] == 1
    assert summary["materialized_setup_count"] == 1
    assert summary["is_actionable"] is False
    assert len(ledger) == 1
    assert ledger.loc[0, "qualification"] == "persistent_bearish"
    assert bool(ledger.loc[0, "candidate_actionable"]) is True
