"""Bounded NSE cash-session source-integrity audit.

This module is audit-only. It does not change TradingCalendar, completed-bar
filtering, detector semantics, weekly authority, scoring, or actionability.

The reference fixture records only dates where NSE cash-market session identity
differs from the ordinary Monday-Friday rule:

* weekday exchange holidays / exceptional closures => expected_session=closed
* announced Saturday/Sunday live sessions          => expected_session=open

Coverage is deliberately bounded to 2021-09-01 through 2026-09-18. The audit
must not be used as a production calendar or as authority for older frozen
history. Its purpose is to quantify source defects before any calendar wiring or
downstream rerun is authorized.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from audit.daily_input_reproducibility import (
    daily_audit_input_manifest_sha256,
    load_daily_audit_input,
    load_daily_audit_input_bundle,
)


NSE_SESSION_SOURCE_INTEGRITY_AUDIT_ID = "nse-session-source-integrity-bounded-v1"
REFERENCE_START_SESSION = date(2021, 9, 1)
REFERENCE_END_SESSION = date(2026, 9, 18)
DEFAULT_REFERENCE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "nse_cash_session_exceptions_2021_09_01_2026_09_18.csv"
)
_REQUIRED_REFERENCE_COLUMNS = {
    "session",
    "expected_session",
    "event_type",
    "source_ref",
}
_REQUIRED_OHLCV_COLUMNS = {"open", "high", "low", "close", "volume"}


@dataclass(frozen=True, slots=True)
class NseSessionIntegritySymbolSummary:
    symbol: str
    source_row_count: int
    first_session: str
    last_session: str
    audited_exception_count: int
    unexpected_closed_row_count: int
    missing_special_session_row_count: int
    unreferenced_weekend_row_count: int
    unexpected_closed_flat_zero_volume_count: int

    @property
    def anomaly_count(self) -> int:
        return (
            self.unexpected_closed_row_count
            + self.missing_special_session_row_count
            + self.unreferenced_weekend_row_count
        )


@dataclass(frozen=True, slots=True)
class NseSessionIntegrityAudit:
    summary: dict[str, object]
    symbol_summaries: pd.DataFrame
    anomalies: pd.DataFrame

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class NseSessionIntegrityPaths:
    summary_json: Path
    symbol_summary_csv: Path
    anomalies_csv: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "summary_json": str(self.summary_json),
            "symbol_summary_csv": str(self.symbol_summary_csv),
            "anomalies_csv": str(self.anomalies_csv),
        }


def _session_date(value: object) -> date:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("session cannot be missing")
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp.normalize().date()


def load_nse_session_exception_reference(
    path: str | Path = DEFAULT_REFERENCE_PATH,
) -> pd.DataFrame:
    reference = pd.read_csv(path, parse_dates=["session"])
    missing = sorted(_REQUIRED_REFERENCE_COLUMNS - set(reference.columns))
    if missing:
        raise ValueError(f"NSE session reference missing columns: {missing}")

    reference = reference.loc[
        :, ["session", "expected_session", "event_type", "source_ref"]
    ].copy()
    reference["session"] = pd.to_datetime(reference["session"]).dt.normalize()
    reference["expected_session"] = (
        reference["expected_session"].astype(str).str.strip().str.lower()
    )
    reference["event_type"] = reference["event_type"].astype(str).str.strip()
    reference["source_ref"] = reference["source_ref"].astype(str).str.strip()

    invalid_expected = sorted(
        set(reference["expected_session"]) - {"open", "closed"}
    )
    if invalid_expected:
        raise ValueError(
            "NSE session reference contains invalid expected_session values: "
            f"{invalid_expected}"
        )
    if reference["session"].duplicated().any():
        duplicate_dates = (
            reference.loc[reference["session"].duplicated(), "session"]
            .dt.date.astype(str)
            .tolist()
        )
        raise ValueError(
            f"NSE session reference contains duplicate dates: {duplicate_dates[:5]}"
        )
    if (reference["event_type"] == "").any() or (reference["source_ref"] == "").any():
        raise ValueError("NSE session reference requires event_type and source_ref")

    actual_start = reference["session"].min().date()
    actual_end = reference["session"].max().date()
    if actual_start < REFERENCE_START_SESSION or actual_end > REFERENCE_END_SESSION:
        raise ValueError("NSE session reference lies outside declared coverage")

    closed_weekends = reference.loc[
        (reference["expected_session"] == "closed")
        & (reference["session"].dt.dayofweek >= 5)
    ]
    if not closed_weekends.empty:
        raise ValueError(
            "closed weekend dates are redundant in an exception-only reference"
        )

    open_weekdays = reference.loc[
        (reference["expected_session"] == "open")
        & (reference["session"].dt.dayofweek < 5)
    ]
    if not open_weekdays.empty:
        raise ValueError(
            "open weekday dates are redundant in an exception-only reference"
        )

    return reference.sort_values("session").reset_index(drop=True)


def _validate_daily(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        raise ValueError("daily source cannot be empty")
    if not isinstance(daily.index, pd.DatetimeIndex):
        raise TypeError("daily source must use a DatetimeIndex")
    missing = sorted(_REQUIRED_OHLCV_COLUMNS - set(daily.columns))
    if missing:
        raise ValueError(f"daily source missing OHLCV columns: {missing}")

    normalized = daily.copy()
    index = pd.DatetimeIndex(pd.to_datetime(normalized.index))
    if index.tz is not None:
        index = index.tz_localize(None)
    normalized.index = index.normalize()
    normalized.index.name = daily.index.name
    normalized.sort_index(inplace=True)
    if normalized.index.has_duplicates:
        raise ValueError("daily source sessions must be unique")
    return normalized


def _row_shape(row: pd.Series) -> tuple[bool, bool]:
    ohlc = tuple(float(row[column]) for column in ("open", "high", "low", "close"))
    flat_ohlc = len(set(ohlc)) == 1
    zero_volume = float(row["volume"]) == 0.0
    return flat_ohlc, zero_volume


def audit_symbol_session_integrity(
    *,
    symbol: str,
    daily: pd.DataFrame,
    reference: pd.DataFrame,
) -> tuple[NseSessionIntegritySymbolSummary, pd.DataFrame]:
    clean_symbol = str(symbol).strip().upper()
    if not clean_symbol:
        raise ValueError("symbol cannot be blank")

    source = _validate_daily(daily)
    first_date = source.index[0].date()
    last_date = source.index[-1].date()
    observed_dates = {timestamp.date() for timestamp in source.index}

    applicable = reference.loc[
        (reference["session"].dt.date >= max(first_date, REFERENCE_START_SESSION))
        & (reference["session"].dt.date <= min(last_date, REFERENCE_END_SESSION))
    ].copy()

    anomaly_rows: list[dict[str, object]] = []
    unexpected_closed_count = 0
    missing_special_count = 0
    flat_zero_count = 0

    for item in applicable.itertuples(index=False):
        session_date = pd.Timestamp(item.session).date()
        present = session_date in observed_dates
        expected = str(item.expected_session)

        if expected == "closed" and present:
            row = source.loc[pd.Timestamp(session_date)]
            flat_ohlc, zero_volume = _row_shape(row)
            unexpected_closed_count += 1
            if flat_ohlc and zero_volume:
                flat_zero_count += 1
            anomaly_rows.append(
                {
                    "symbol": clean_symbol,
                    "session": session_date.isoformat(),
                    "anomaly": "UNEXPECTED_CLOSED_SESSION_ROW",
                    "expected_session": expected,
                    "event_type": str(item.event_type),
                    "source_ref": str(item.source_ref),
                    "flat_ohlc": flat_ohlc,
                    "zero_volume": zero_volume,
                }
            )
        elif expected == "open" and not present:
            missing_special_count += 1
            anomaly_rows.append(
                {
                    "symbol": clean_symbol,
                    "session": session_date.isoformat(),
                    "anomaly": "MISSING_SPECIAL_SESSION_ROW",
                    "expected_session": expected,
                    "event_type": str(item.event_type),
                    "source_ref": str(item.source_ref),
                    "flat_ohlc": False,
                    "zero_volume": False,
                }
            )

    referenced_open_weekends = {
        pd.Timestamp(value).date()
        for value in reference.loc[
            reference["expected_session"] == "open", "session"
        ]
    }
    unreferenced_weekends = sorted(
        session_date
        for session_date in observed_dates
        if REFERENCE_START_SESSION <= session_date <= REFERENCE_END_SESSION
        and session_date.weekday() >= 5
        and session_date not in referenced_open_weekends
    )
    for session_date in unreferenced_weekends:
        row = source.loc[pd.Timestamp(session_date)]
        flat_ohlc, zero_volume = _row_shape(row)
        anomaly_rows.append(
            {
                "symbol": clean_symbol,
                "session": session_date.isoformat(),
                "anomaly": "UNREFERENCED_WEEKEND_ROW",
                "expected_session": "unknown",
                "event_type": "unreferenced_weekend",
                "source_ref": "",
                "flat_ohlc": flat_ohlc,
                "zero_volume": zero_volume,
            }
        )

    anomalies = pd.DataFrame(
        anomaly_rows,
        columns=[
            "symbol",
            "session",
            "anomaly",
            "expected_session",
            "event_type",
            "source_ref",
            "flat_ohlc",
            "zero_volume",
        ],
    )
    summary = NseSessionIntegritySymbolSummary(
        symbol=clean_symbol,
        source_row_count=len(source),
        first_session=first_date.isoformat(),
        last_session=last_date.isoformat(),
        audited_exception_count=len(applicable),
        unexpected_closed_row_count=unexpected_closed_count,
        missing_special_session_row_count=missing_special_count,
        unreferenced_weekend_row_count=len(unreferenced_weekends),
        unexpected_closed_flat_zero_volume_count=flat_zero_count,
    )
    return summary, anomalies


def run_nse_session_integrity_universe(
    *,
    input_snapshot_dir: str | Path,
    reference_path: str | Path = DEFAULT_REFERENCE_PATH,
) -> NseSessionIntegrityAudit:
    input_root = Path(input_snapshot_dir)
    reference = load_nse_session_exception_reference(reference_path)
    bundle = load_daily_audit_input_bundle(input_root)

    symbol_summaries: list[NseSessionIntegritySymbolSummary] = []
    anomaly_frames: list[pd.DataFrame] = []

    for fingerprint in bundle.fingerprints:
        daily = load_daily_audit_input(input_root, fingerprint.symbol)
        symbol_summary, anomalies = audit_symbol_session_integrity(
            symbol=fingerprint.symbol,
            daily=daily,
            reference=reference,
        )
        symbol_summaries.append(symbol_summary)
        if not anomalies.empty:
            anomaly_frames.append(anomalies)

    symbol_frame = pd.DataFrame([asdict(item) for item in symbol_summaries])
    anomalies = (
        pd.concat(anomaly_frames, ignore_index=True)
        if anomaly_frames
        else pd.DataFrame(
            columns=[
                "symbol",
                "session",
                "anomaly",
                "expected_session",
                "event_type",
                "source_ref",
                "flat_ohlc",
                "zero_volume",
            ]
        )
    )

    first_snapshot_session = min(
        pd.Timestamp(item.first_session).date()
        for item in bundle.fingerprints
        if item.first_session is not None
    )
    last_snapshot_session = max(
        pd.Timestamp(item.last_session).date()
        for item in bundle.fingerprints
        if item.last_session is not None
    )
    full_history_covered = (
        first_snapshot_session >= REFERENCE_START_SESSION
        and last_snapshot_session <= REFERENCE_END_SESSION
    )

    anomaly_counts = (
        anomalies["anomaly"].value_counts().to_dict()
        if not anomalies.empty
        else {}
    )
    summary: dict[str, object] = {
        "audit_id": NSE_SESSION_SOURCE_INTEGRITY_AUDIT_ID,
        "is_actionable": False,
        "study_complete": True,
        "input_snapshot_basket": bundle.basket_name,
        "input_snapshot_provider": bundle.provider,
        "input_snapshot_cutoff": bundle.cutoff,
        "input_snapshot_manifest_sha256": daily_audit_input_manifest_sha256(
            input_root
        ),
        "symbol_count": bundle.symbol_count,
        "reference_start_session": REFERENCE_START_SESSION.isoformat(),
        "reference_end_session": REFERENCE_END_SESSION.isoformat(),
        "reference_exception_count": len(reference),
        "reference_closed_date_count": int(
            (reference["expected_session"] == "closed").sum()
        ),
        "reference_special_session_count": int(
            (reference["expected_session"] == "open").sum()
        ),
        "first_snapshot_session": first_snapshot_session.isoformat(),
        "last_snapshot_session": last_snapshot_session.isoformat(),
        "reference_window_covers_full_snapshot_history": full_history_covered,
        "unexpected_closed_session_row_count": int(
            anomaly_counts.get("UNEXPECTED_CLOSED_SESSION_ROW", 0)
        ),
        "missing_special_session_row_count": int(
            anomaly_counts.get("MISSING_SPECIAL_SESSION_ROW", 0)
        ),
        "unreferenced_weekend_row_count": int(
            anomaly_counts.get("UNREFERENCED_WEEKEND_ROW", 0)
        ),
        "unexpected_closed_flat_zero_volume_row_count": int(
            symbol_frame["unexpected_closed_flat_zero_volume_count"].sum()
        ),
        "production_calendar_change_authorized": False,
        "downstream_rerun_authorized": False,
        "scope_note": (
            "Bounded source-integrity audit only; extend authoritative session "
            "coverage across full frozen history before production calendar wiring."
        ),
    }
    return NseSessionIntegrityAudit(
        summary=summary,
        symbol_summaries=symbol_frame,
        anomalies=anomalies,
    )


def write_nse_session_integrity_bundle(
    audit: NseSessionIntegrityAudit,
    *,
    output_dir: str | Path,
) -> NseSessionIntegrityPaths:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = NseSessionIntegrityPaths(
        summary_json=root / "nse_session_integrity_summary.json",
        symbol_summary_csv=root / "nse_session_integrity_symbols.csv",
        anomalies_csv=root / "nse_session_integrity_anomalies.csv",
    )
    paths.summary_json.write_text(
        json.dumps(audit.summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    audit.symbol_summaries.to_csv(paths.symbol_summary_csv, index=False)
    audit.anomalies.to_csv(paths.anomalies_csv, index=False)
    return paths


__all__ = [
    "DEFAULT_REFERENCE_PATH",
    "NSE_SESSION_SOURCE_INTEGRITY_AUDIT_ID",
    "NseSessionIntegrityAudit",
    "NseSessionIntegrityPaths",
    "NseSessionIntegritySymbolSummary",
    "REFERENCE_END_SESSION",
    "REFERENCE_START_SESSION",
    "audit_symbol_session_integrity",
    "load_nse_session_exception_reference",
    "run_nse_session_integrity_universe",
    "write_nse_session_integrity_bundle",
]
