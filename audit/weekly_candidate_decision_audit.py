"""Audit every production weekly scanner candidate before WeeklySetup materialization.

This module is analysis-only. It exposes existing candidate qualification,
actionability, VSA freshness/conflict outcomes, and materialization results
without changing production scanner semantics.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

import pandas as pd

from audit.genuine_daily_sequence_case import (
    ProductionWeeklySourceFingerprint,
    fingerprint_production_weekly_source,
)
from background.qualification import PatternQualification
from daily_completion import completed_daily_only
from data import completed_weekly_only, daily_to_weekly
from historical_scanner import HistoricalScannerRunner
from metrics_engine import MetricsEngine
from scanner import ScannerCandidate
from trading_calendar import NSETradingCalendar, TradingCalendar
from weekly_setup_materializer import materialize_production_weekly_setup


WEEKLY_CANDIDATE_DECISION_AUDIT_ID = "production-weekly-candidate-decision-ledger-v1"


class _HistoricalRunner(Protocol):
    def scan(self, metrics: pd.DataFrame) -> list[ScannerCandidate]:
        ...


class _MetricsEngine(Protocol):
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        ...


@dataclass(frozen=True, slots=True)
class WeeklyCandidateDecisionRow:
    bar_index: int | None
    week: str | None
    qualification: PatternQualification
    qualification_actionable_evidence: bool
    candidate_actionable: bool
    materializes_weekly_setup: bool
    materialized_direction: str | None
    confidence: float
    net_strength: float
    net_pressure: float
    scoring_bar_index: int | None
    scoring_evidence_age: int | None
    used_fallback_evidence: bool
    signal_bar_anomaly: bool
    reason: str
    qualifying_evidence_codes: str
    scoring_evidence_codes: str


@dataclass(frozen=True, slots=True)
class WeeklyCandidateDecisionAudit:
    symbol: str
    audit_id: str
    source_fingerprint: ProductionWeeklySourceFingerprint
    candidate_count: int
    qualification_counts: dict[str, int]
    actionable_counts: dict[str, int]
    materialized_direction_counts: dict[str, int]
    signal_bar_anomaly_count: int
    fallback_evidence_count: int
    persistent_bullish_reason_counts: dict[str, int]
    persistent_bearish_reason_counts: dict[str, int]
    rows: tuple[WeeklyCandidateDecisionRow, ...]

    @property
    def materialized_setup_count(self) -> int:
        return sum(self.materialized_direction_counts.values())

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class WeeklyCandidateDecisionAuditPaths:
    summary_json: Path
    candidate_ledger_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "candidate_ledger_csv": str(self.candidate_ledger_csv),
        }


def _normalize_symbol(symbol: str) -> str:
    clean = str(symbol).strip().upper()
    if not clean:
        raise ValueError("symbol cannot be blank")
    return clean


def _code_text(values: tuple[str, ...]) -> str:
    return ";".join(values)


def _row_for_candidate(
    *,
    candidate: ScannerCandidate,
    symbol: str,
) -> WeeklyCandidateDecisionRow:
    setup = materialize_production_weekly_setup(
        candidate,
        symbol=symbol,
    )
    return WeeklyCandidateDecisionRow(
        bar_index=candidate.bar_index,
        week=candidate.week,
        qualification=candidate.qualification,
        qualification_actionable_evidence=(
            candidate.qualification_result.is_actionable_evidence
        ),
        candidate_actionable=candidate.actionable,
        materializes_weekly_setup=setup is not None,
        materialized_direction=None if setup is None else setup.direction.value,
        confidence=float(candidate.confidence),
        net_strength=float(candidate.net_strength),
        net_pressure=float(candidate.net_pressure),
        scoring_bar_index=candidate.scoring_bar_index,
        scoring_evidence_age=candidate.scoring_evidence_age,
        used_fallback_evidence=bool(candidate.used_fallback_evidence),
        signal_bar_anomaly=bool(candidate.signal_bar_anomaly),
        reason=candidate.reason,
        qualifying_evidence_codes=_code_text(
            tuple(candidate.qualifying_evidence_codes)
        ),
        scoring_evidence_codes=_code_text(
            tuple(candidate.scoring_evidence_codes)
        ),
    )


def audit_weekly_candidate_decisions(
    *,
    symbol: str,
    candidates: tuple[ScannerCandidate, ...],
    source_fingerprint: ProductionWeeklySourceFingerprint,
) -> WeeklyCandidateDecisionAudit:
    """Summarize final candidate decisions without rerunning decision logic."""

    clean_symbol = _normalize_symbol(symbol)
    rows = tuple(
        _row_for_candidate(candidate=candidate, symbol=clean_symbol)
        for candidate in candidates
    )

    qualification_counter = Counter(
        row.qualification.value for row in rows
    )
    actionable_counter = Counter(
        row.qualification.value
        for row in rows
        if row.candidate_actionable
    )
    materialized_counter = Counter(
        row.materialized_direction
        for row in rows
        if row.materializes_weekly_setup
        and row.materialized_direction is not None
    )
    qualification_counts = {
        item.value: qualification_counter[item.value]
        for item in PatternQualification
    }
    actionable_counts = {
        item.value: actionable_counter[item.value]
        for item in PatternQualification
    }
    materialized_counts = {
        "bullish": materialized_counter["bullish"],
        "bearish": materialized_counter["bearish"],
    }

    bullish_reasons = Counter(
        row.reason
        for row in rows
        if row.qualification is PatternQualification.PERSISTENT_BULLISH
    )
    bearish_reasons = Counter(
        row.reason
        for row in rows
        if row.qualification is PatternQualification.PERSISTENT_BEARISH
    )

    return WeeklyCandidateDecisionAudit(
        symbol=clean_symbol,
        audit_id=WEEKLY_CANDIDATE_DECISION_AUDIT_ID,
        source_fingerprint=source_fingerprint,
        candidate_count=len(rows),
        qualification_counts=dict(sorted(qualification_counts.items())),
        actionable_counts=dict(sorted(actionable_counts.items())),
        materialized_direction_counts=dict(sorted(materialized_counts.items())),
        signal_bar_anomaly_count=sum(
            1 for row in rows if row.signal_bar_anomaly
        ),
        fallback_evidence_count=sum(
            1 for row in rows if row.used_fallback_evidence
        ),
        persistent_bullish_reason_counts=dict(
            sorted(bullish_reasons.items())
        ),
        persistent_bearish_reason_counts=dict(
            sorted(bearish_reasons.items())
        ),
        rows=rows,
    )


def build_weekly_candidate_decision_audit(
    *,
    symbol: str,
    daily: pd.DataFrame,
    now: datetime | pd.Timestamp | str | None = None,
    calendar: TradingCalendar | None = None,
    historical_runner: _HistoricalRunner | None = None,
    metrics_engine: _MetricsEngine | None = None,
) -> WeeklyCandidateDecisionAudit:
    """Run the existing completed-weekly production scanner and audit outputs."""

    clean_symbol = _normalize_symbol(symbol)
    exchange_calendar = calendar or NSETradingCalendar()
    completed_daily = completed_daily_only(
        daily,
        now=now,
        calendar=exchange_calendar,
    )
    if completed_daily.empty:
        raise ValueError("no completed daily bars are available")

    weekly = daily_to_weekly(completed_daily)
    completed_weekly = completed_weekly_only(
        weekly,
        now=now,
    )
    if completed_weekly.empty:
        raise ValueError("no completed weekly bars are available")

    engine = metrics_engine or MetricsEngine()
    metrics = engine.calculate(completed_weekly)
    runner = historical_runner or HistoricalScannerRunner()
    candidates = tuple(runner.scan(metrics))

    return audit_weekly_candidate_decisions(
        symbol=clean_symbol,
        candidates=candidates,
        source_fingerprint=fingerprint_production_weekly_source(
            symbol=clean_symbol,
            completed_weekly=completed_weekly,
        ),
    )


def _row_payload(row: WeeklyCandidateDecisionRow) -> dict[str, object]:
    payload = asdict(row)
    payload["qualification"] = row.qualification.value
    return payload


def write_weekly_candidate_decision_audit(
    audit: WeeklyCandidateDecisionAudit,
    output_dir: str | Path,
) -> WeeklyCandidateDecisionAuditPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = WeeklyCandidateDecisionAuditPaths(
        summary_json=root / "weekly_candidate_decision_summary.json",
        candidate_ledger_csv=root / "weekly_candidate_decision_ledger.csv",
    )

    payload = {
        "symbol": audit.symbol,
        "audit_id": audit.audit_id,
        "candidate_count": audit.candidate_count,
        "qualification_counts": audit.qualification_counts,
        "actionable_counts": audit.actionable_counts,
        "materialized_setup_count": audit.materialized_setup_count,
        "materialized_direction_counts": audit.materialized_direction_counts,
        "signal_bar_anomaly_count": audit.signal_bar_anomaly_count,
        "fallback_evidence_count": audit.fallback_evidence_count,
        "persistent_bullish_reason_counts": (
            audit.persistent_bullish_reason_counts
        ),
        "persistent_bearish_reason_counts": (
            audit.persistent_bearish_reason_counts
        ),
        "production_weekly_source_fingerprint": (
            audit.source_fingerprint.sha256
        ),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    pd.DataFrame(
        [_row_payload(row) for row in audit.rows],
        columns=(
            "bar_index",
            "week",
            "qualification",
            "qualification_actionable_evidence",
            "candidate_actionable",
            "materializes_weekly_setup",
            "materialized_direction",
            "confidence",
            "net_strength",
            "net_pressure",
            "scoring_bar_index",
            "scoring_evidence_age",
            "used_fallback_evidence",
            "signal_bar_anomaly",
            "reason",
            "qualifying_evidence_codes",
            "scoring_evidence_codes",
        ),
    ).to_csv(paths.candidate_ledger_csv, index=False)
    return paths


__all__ = [
    "WEEKLY_CANDIDATE_DECISION_AUDIT_ID",
    "WeeklyCandidateDecisionAudit",
    "WeeklyCandidateDecisionAuditPaths",
    "WeeklyCandidateDecisionRow",
    "audit_weekly_candidate_decisions",
    "build_weekly_candidate_decision_audit",
    "write_weekly_candidate_decision_audit",
]
