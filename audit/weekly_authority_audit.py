"""Audit production weekly setup authority versus daily coordinator selection.

This module is analysis-only. It reuses K8 production weekly setup derivation and
K6 causal daily assignment without modifying either path.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

import pandas as pd

from audit.genuine_daily_sequence_case import (
    HistoricalProductionWeeklySetupArchive,
    derive_historical_production_weekly_setups,
)
from scanner import ScannerCandidate
from audit.weekly_direction_assignments import (
    CausalWeeklyDirectionArchive,
    produce_causal_weekly_direction_assignments,
)
from trading_calendar import NSETradingCalendar, TradingCalendar
from weekly_daily_coordinator import (
    weekly_setup_available_session,
    weekly_setup_completion_session,
)
from weekly_setup import WeeklySetup, WeeklySetupDirection


WEEKLY_AUTHORITY_AUDIT_ID = "production-weekly-authority-ledger-v1"


class _HistoricalRunner(Protocol):
    def scan(self, metrics: pd.DataFrame) -> list[ScannerCandidate]:
        ...


class _MetricsEngine(Protocol):
    def calculate(self, df: pd.DataFrame) -> pd.DataFrame:
        ...


@dataclass(frozen=True, slots=True)
class WeeklyAuthorityAuditRow:
    setup_id: str
    signal_week: str
    direction: WeeklySetupDirection
    qualification: str
    status: str
    completion_session: str
    available_session: str
    selected_daily_count: int
    first_selected_session: str | None
    last_selected_session: str | None


@dataclass(frozen=True, slots=True)
class WeeklyAuthorityAudit:
    symbol: str
    audit_id: str
    candidate_count: int
    setup_count: int
    bullish_setup_count: int
    bearish_setup_count: int
    selected_setup_count: int
    unselected_setup_count: int
    assignment_count: int
    bullish_assignment_count: int
    bearish_assignment_count: int
    production_weekly_source_fingerprint: str
    weekly_direction_source_fingerprint: str
    rows: tuple[WeeklyAuthorityAuditRow, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class WeeklyAuthorityAuditPaths:
    summary_json: Path
    setup_ledger_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "setup_ledger_csv": str(self.setup_ledger_csv),
        }


def _build_rows(
    *,
    setups: tuple[WeeklySetup, ...],
    assignments: CausalWeeklyDirectionArchive,
    calendar: TradingCalendar,
) -> tuple[WeeklyAuthorityAuditRow, ...]:
    selected_sessions: dict[str, list[str]] = defaultdict(list)
    for observation in assignments.observations:
        selected_sessions[observation.setup_id].append(observation.session)

    rows: list[WeeklyAuthorityAuditRow] = []
    for setup in setups:
        sessions = selected_sessions.get(setup.setup_id, [])
        completion = weekly_setup_completion_session(setup, calendar=calendar)
        available = weekly_setup_available_session(setup, calendar=calendar)
        rows.append(
            WeeklyAuthorityAuditRow(
                setup_id=setup.setup_id,
                signal_week=setup.signal_week,
                direction=setup.direction,
                qualification=setup.qualification.value,
                status=setup.status.value,
                completion_session=completion.isoformat(),
                available_session=available.isoformat(),
                selected_daily_count=len(sessions),
                first_selected_session=sessions[0] if sessions else None,
                last_selected_session=sessions[-1] if sessions else None,
            )
        )

    return tuple(
        sorted(
            rows,
            key=lambda item: (
                item.completion_session,
                item.setup_id,
            ),
        )
    )


def build_weekly_authority_audit(
    *,
    symbol: str,
    daily: pd.DataFrame,
    now: datetime | pd.Timestamp | str | None = None,
    calendar: TradingCalendar | None = None,
    historical_runner: _HistoricalRunner | None = None,
    metrics_engine: _MetricsEngine | None = None,
) -> WeeklyAuthorityAudit:
    """Audit setup creation separately from point-in-time daily authority."""

    exchange_calendar = calendar or NSETradingCalendar()
    weekly_archive: HistoricalProductionWeeklySetupArchive = (
        derive_historical_production_weekly_setups(
            symbol=symbol,
            daily=daily,
            now=now,
            calendar=exchange_calendar,
            historical_runner=historical_runner,
            metrics_engine=metrics_engine,
        )
    )
    assignments = produce_causal_weekly_direction_assignments(
        symbol=weekly_archive.symbol,
        daily=daily,
        setups=weekly_archive.setups,
        now=now,
        calendar=exchange_calendar,
    )

    rows = _build_rows(
        setups=weekly_archive.setups,
        assignments=assignments,
        calendar=exchange_calendar,
    )
    setup_counts = Counter(setup.direction for setup in weekly_archive.setups)
    assignment_counts = Counter(
        item.direction for item in assignments.observations
    )
    selected_setup_count = sum(
        1 for row in rows if row.selected_daily_count > 0
    )

    return WeeklyAuthorityAudit(
        symbol=weekly_archive.symbol,
        audit_id=WEEKLY_AUTHORITY_AUDIT_ID,
        candidate_count=weekly_archive.candidate_count,
        setup_count=weekly_archive.setup_count,
        bullish_setup_count=setup_counts[WeeklySetupDirection.BULLISH],
        bearish_setup_count=setup_counts[WeeklySetupDirection.BEARISH],
        selected_setup_count=selected_setup_count,
        unselected_setup_count=weekly_archive.setup_count - selected_setup_count,
        assignment_count=assignments.assignment_count,
        bullish_assignment_count=assignment_counts[
            WeeklySetupDirection.BULLISH
        ],
        bearish_assignment_count=assignment_counts[
            WeeklySetupDirection.BEARISH
        ],
        production_weekly_source_fingerprint=(
            weekly_archive.source_fingerprint.sha256
        ),
        weekly_direction_source_fingerprint=(
            assignments.source_fingerprint.sha256
        ),
        rows=rows,
    )


def _row_payload(row: WeeklyAuthorityAuditRow) -> dict[str, object]:
    payload = asdict(row)
    payload["direction"] = row.direction.value
    return payload


def write_weekly_authority_audit(
    audit: WeeklyAuthorityAudit,
    output_dir: str | Path,
) -> WeeklyAuthorityAuditPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = WeeklyAuthorityAuditPaths(
        summary_json=root / "weekly_authority_summary.json",
        setup_ledger_csv=root / "weekly_setup_authority_ledger.csv",
    )

    summary = {
        "symbol": audit.symbol,
        "audit_id": audit.audit_id,
        "candidate_count": audit.candidate_count,
        "setup_count": audit.setup_count,
        "setup_direction_counts": {
            "bullish": audit.bullish_setup_count,
            "bearish": audit.bearish_setup_count,
        },
        "selected_setup_count": audit.selected_setup_count,
        "unselected_setup_count": audit.unselected_setup_count,
        "assignment_count": audit.assignment_count,
        "assignment_direction_counts": {
            "bullish": audit.bullish_assignment_count,
            "bearish": audit.bearish_assignment_count,
        },
        "production_weekly_source_fingerprint": (
            audit.production_weekly_source_fingerprint
        ),
        "weekly_direction_source_fingerprint": (
            audit.weekly_direction_source_fingerprint
        ),
        "is_actionable": False,
    }
    paths.summary_json.write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    pd.DataFrame(
        [_row_payload(row) for row in audit.rows],
        columns=(
            "setup_id",
            "signal_week",
            "direction",
            "qualification",
            "status",
            "completion_session",
            "available_session",
            "selected_daily_count",
            "first_selected_session",
            "last_selected_session",
        ),
    ).to_csv(paths.setup_ledger_csv, index=False)
    return paths


__all__ = [
    "WEEKLY_AUTHORITY_AUDIT_ID",
    "WeeklyAuthorityAudit",
    "WeeklyAuthorityAuditPaths",
    "WeeklyAuthorityAuditRow",
    "build_weekly_authority_audit",
    "write_weekly_authority_audit",
]
