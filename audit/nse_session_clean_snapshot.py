"""Build an immutable NSE-session-clean v2 snapshot from the frozen audit source.

This module is audit/data-preparation only. It does not change production
TradingCalendar behavior, detector semantics, weekly authority, scoring, or
actionability.

The v2 snapshot is derived from one exact frozen baseline manifest:

1. remove rows on NSE cash-market dates explicitly marked closed by the bounded
   session-exception reference;
2. retain already-present special weekend sessions;
3. backfill only missing special sessions from user-supplied official NSE
   bhavcopy files;
4. write a new compatible daily-audit snapshot bundle with deterministic
   fingerprints and repair provenance.

The original frozen snapshot is never mutated.
"""

from __future__ import annotations

import io
import json
import math
import re
import zipfile
from dataclasses import asdict, dataclass
from datetime import date
from hashlib import sha256
from pathlib import Path
from statistics import median
from typing import Iterable, Sequence

import pandas as pd

from audit.daily_input_reproducibility import (
    DAILY_AUDIT_INPUT_SNAPSHOT_ID,
    DailyAuditInputBundle,
    DailyAuditInputFingerprint,
    daily_audit_input_manifest_sha256,
    fingerprint_daily_audit_input,
    load_daily_audit_input,
    load_daily_audit_input_bundle,
)
from audit.nse_session_integrity import (
    DEFAULT_REFERENCE_PATH,
    load_nse_session_exception_reference,
)


NSE_SESSION_CLEAN_SNAPSHOT_VERSION = "nse-session-clean-v2"
EXPECTED_BASELINE_MANIFEST_SHA256 = (
    "45bb7123d2b3b570cf58241f09cb6175f6052d792f92728b194fc587762fb8ff"
)
DEFAULT_ALIAS_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "nse_session_backfill_symbol_aliases.csv"
)
_REQUIRED_DAILY_COLUMNS = ("open", "high", "low", "close", "volume")

_SYMBOL_COLUMNS = (
    "SYMBOL",
    "Symbol",
    "symbol",
    "TckrSymb",
    "TCKRSYMB",
)
_SERIES_COLUMNS = (
    "SERIES",
    "Series",
    "series",
    "SctySrs",
    "SCTYSRS",
)
_OPEN_COLUMNS = ("OPEN", "OPEN_PRICE", "Open", "OpnPric", "OPNPRIC")
_HIGH_COLUMNS = ("HIGH", "HIGH_PRICE", "High", "HghPric", "HGHPRIC")
_LOW_COLUMNS = ("LOW", "LOW_PRICE", "Low", "LwPric", "LWPRIC")
_CLOSE_COLUMNS = (
    "CLOSE",
    "CLOSE_PRICE",
    "Close",
    "ClsPric",
    "CLSPRIC",
)
_VOLUME_COLUMNS = (
    "TOTTRDQTY",
    "TTL_TRD_QNTY",
    "TOTTRD_QTY",
    "Volume",
    "volume",
    "TtlTradgVol",
    "TTLTRADGVOL",
)
_DATE_COLUMNS = (
    "TIMESTAMP",
    "DATE1",
    "Date",
    "date",
    "TradDt",
    "TRADDT",
    "BizDt",
    "BIZDT",
)

_FILENAME_DATE_PATTERNS = (
    re.compile(r"(?P<day>\d{2})(?P<mon>[A-Z]{3})(?P<year>\d{4})", re.I),
    re.compile(r"(?P<year>\d{4})(?P<mon>\d{2})(?P<day>\d{2})"),
)

_BACKFILL_CALIBRATION_SESSION = {
    date(2023, 11, 12): date(2023, 11, 10),
    date(2024, 1, 20): date(2024, 1, 19),
    date(2024, 3, 2): date(2024, 3, 1),
    date(2024, 5, 18): date(2024, 5, 17),
    date(2026, 2, 1): date(2026, 1, 30),
}


@dataclass(frozen=True, slots=True)
class OfficialBhavcopySource:
    path: str
    sha256: str
    normalized_row_count: int
    sessions: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class SessionRepairRecord:
    symbol: str
    session: str
    action: str
    nse_symbol: str
    source_path: str
    source_sha256: str
    source_ref: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    calibration_session: str = ""
    calibration_source_path: str = ""
    calibration_source_sha256: str = ""
    price_scale: float = 1.0
    volume_scale: float = 1.0


@dataclass(frozen=True, slots=True)
class SessionCleanSnapshotBuild:
    output_dir: Path
    manifest_json: Path
    manifest_csv: Path
    repairs_csv: Path
    source_files_csv: Path
    baseline_manifest_sha256: str
    output_manifest_sha256: str
    symbol_count: int
    removed_row_count: int
    added_row_count: int

    @property
    def is_actionable(self) -> bool:
        return False


def _first_present(columns: Iterable[str], candidates: Sequence[str]) -> str | None:
    available = set(columns)
    for candidate in candidates:
        if candidate in available:
            return candidate
    return None


def _parse_session_series(series: pd.Series) -> pd.Series:
    values = pd.to_datetime(series, errors="coerce", dayfirst=False)
    if values.isna().all():
        values = pd.to_datetime(series, errors="coerce", dayfirst=True)
    if values.isna().any():
        raise ValueError("bhavcopy contains unparseable session values")
    if getattr(values.dt, "tz", None) is not None:
        values = values.dt.tz_localize(None)
    return values.dt.normalize()


def _session_from_filename(name: str) -> pd.Timestamp | None:
    basename = Path(name).name.upper()
    for pattern in _FILENAME_DATE_PATTERNS:
        match = pattern.search(basename)
        if match is None:
            continue
        parts = match.groupdict()
        if parts["mon"].isalpha():
            value = f"{parts['day']}-{parts['mon']}-{parts['year']}"
            parsed = pd.to_datetime(value, format="%d-%b-%Y", errors="coerce")
        else:
            value = f"{parts['year']}-{parts['mon']}-{parts['day']}"
            parsed = pd.to_datetime(value, format="%Y-%m-%d", errors="coerce")
        if not pd.isna(parsed):
            return pd.Timestamp(parsed).normalize()
    return None


def normalize_official_bhavcopy_frame(
    frame: pd.DataFrame,
    *,
    source_name: str,
) -> pd.DataFrame:
    """Normalize legacy NSE CM or UDiFF bhavcopy rows to one audit schema."""

    frame = frame.copy()
    frame.columns = [
        str(column).replace("\ufeff", "").strip()
        for column in frame.columns
    ]

    symbol_col = _first_present(frame.columns, _SYMBOL_COLUMNS)
    series_col = _first_present(frame.columns, _SERIES_COLUMNS)
    open_col = _first_present(frame.columns, _OPEN_COLUMNS)
    high_col = _first_present(frame.columns, _HIGH_COLUMNS)
    low_col = _first_present(frame.columns, _LOW_COLUMNS)
    close_col = _first_present(frame.columns, _CLOSE_COLUMNS)
    volume_col = _first_present(frame.columns, _VOLUME_COLUMNS)
    date_col = _first_present(frame.columns, _DATE_COLUMNS)

    required = {
        "symbol": symbol_col,
        "series": series_col,
        "open": open_col,
        "high": high_col,
        "low": low_col,
        "close": close_col,
        "volume": volume_col,
    }
    missing = sorted(name for name, value in required.items() if value is None)
    if missing:
        raise ValueError(
            f"{source_name}: unsupported bhavcopy schema; missing {missing}"
        )

    normalized = pd.DataFrame(
        {
            "nse_symbol": frame[symbol_col].astype(str).str.strip().str.upper(),
            "series": frame[series_col].astype(str).str.strip().str.upper(),
            "open": pd.to_numeric(frame[open_col], errors="coerce"),
            "high": pd.to_numeric(frame[high_col], errors="coerce"),
            "low": pd.to_numeric(frame[low_col], errors="coerce"),
            "close": pd.to_numeric(frame[close_col], errors="coerce"),
            "volume": pd.to_numeric(frame[volume_col], errors="coerce"),
        }
    )

    if date_col is not None:
        normalized["session"] = _parse_session_series(frame[date_col])
    else:
        session = _session_from_filename(source_name)
        if session is None:
            raise ValueError(
                f"{source_name}: bhavcopy has no recognized date column "
                "and filename does not encode a session"
            )
        normalized["session"] = session

    normalized = normalized.loc[normalized["series"] == "EQ"].copy()
    normalized = normalized.loc[normalized["nse_symbol"] != ""].copy()
    if normalized.empty:
        raise ValueError(f"{source_name}: no EQ-series rows found")

    numeric_columns = ["open", "high", "low", "close", "volume"]
    if normalized[numeric_columns].isna().any().any():
        raise ValueError(f"{source_name}: EQ rows contain missing OHLCV values")

    for column in ("open", "high", "low", "close"):
        if not normalized[column].map(math.isfinite).all():
            raise ValueError(f"{source_name}: {column} contains non-finite values")
        if (normalized[column] <= 0).any():
            raise ValueError(f"{source_name}: {column} must be positive")
    if not normalized["volume"].map(math.isfinite).all():
        raise ValueError(f"{source_name}: volume contains non-finite values")
    if (normalized["volume"] < 0).any():
        raise ValueError(f"{source_name}: volume cannot be negative")

    key = ["session", "nse_symbol", "series"]
    duplicates = normalized.duplicated(key, keep=False)
    if duplicates.any():
        duplicate_keys = (
            normalized.loc[duplicates, key]
            .astype(str)
            .agg("|".join, axis=1)
            .drop_duplicates()
            .tolist()
        )
        raise ValueError(
            f"{source_name}: duplicate EQ identities: {duplicate_keys[:5]}"
        )

    return normalized.sort_values(key).reset_index(drop=True)


def _frames_from_source(path: Path) -> list[tuple[str, pd.DataFrame]]:
    if path.suffix.lower() == ".csv":
        return [(path.name, pd.read_csv(path))]

    if path.suffix.lower() != ".zip":
        raise ValueError(f"unsupported bhavcopy file type: {path}")

    frames: list[tuple[str, pd.DataFrame]] = []
    with zipfile.ZipFile(path) as archive:
        for member in archive.namelist():
            if not member.lower().endswith(".csv"):
                continue
            with archive.open(member) as handle:
                payload = handle.read()
            try:
                frame = pd.read_csv(io.BytesIO(payload))
            except Exception:
                continue
            frames.append((member, frame))
    if not frames:
        raise ValueError(f"{path}: zip contains no readable CSV members")
    return frames


def load_official_bhavcopy_sources(
    paths: Sequence[str | Path],
) -> tuple[pd.DataFrame, tuple[OfficialBhavcopySource, ...]]:
    """Load exactly the official source files supplied for the missing sessions."""

    if not paths:
        raise ValueError("at least one official bhavcopy source is required")

    normalized_frames: list[pd.DataFrame] = []
    source_records: list[OfficialBhavcopySource] = []

    for raw_path in paths:
        path = Path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        digest = sha256(path.read_bytes()).hexdigest()
        accepted: list[pd.DataFrame] = []
        accepted_names: list[str] = []
        errors: list[str] = []

        for member_name, frame in _frames_from_source(path):
            source_name = f"{path.name}:{member_name}"
            try:
                normalized = normalize_official_bhavcopy_frame(
                    frame,
                    source_name=source_name,
                )
            except ValueError as exc:
                errors.append(str(exc))
                continue
            normalized = normalized.copy()
            normalized["source_path"] = str(path)
            normalized["source_sha256"] = digest
            normalized["source_member"] = member_name
            accepted.append(normalized)
            accepted_names.append(member_name)

        if len(accepted) != 1:
            detail = "; ".join(errors[:3])
            raise ValueError(
                f"{path}: expected exactly one recognizable CM bhavcopy CSV "
                f"member, found {len(accepted)} ({accepted_names}); {detail}"
            )

        normalized = accepted[0]
        normalized_frames.append(normalized)
        source_records.append(
            OfficialBhavcopySource(
                path=str(path),
                sha256=digest,
                normalized_row_count=len(normalized),
                sessions=tuple(
                    sorted(
                        {
                            pd.Timestamp(value).date().isoformat()
                            for value in normalized["session"]
                        }
                    )
                ),
            )
        )

    combined = pd.concat(normalized_frames, ignore_index=True)
    duplicate_key = ["session", "nse_symbol", "series"]
    duplicated = combined.duplicated(duplicate_key, keep=False)
    if duplicated.any():
        keys = (
            combined.loc[duplicated, duplicate_key]
            .astype(str)
            .agg("|".join, axis=1)
            .drop_duplicates()
            .tolist()
        )
        raise ValueError(
            "official bhavcopy sources overlap on EQ identities: "
            f"{keys[:5]}"
        )
    return combined, tuple(source_records)


def load_backfill_aliases(
    path: str | Path = DEFAULT_ALIAS_PATH,
) -> dict[tuple[str, date], str]:
    frame = pd.read_csv(path, parse_dates=["session"])
    required = {"snapshot_symbol", "session", "nse_symbol"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"backfill alias file missing columns: {missing}")

    aliases: dict[tuple[str, date], str] = {}
    for item in frame.itertuples(index=False):
        snapshot_symbol = str(item.snapshot_symbol).strip().upper()
        nse_symbol = str(item.nse_symbol).strip().upper()
        session = pd.Timestamp(item.session).date()
        if not snapshot_symbol or not nse_symbol:
            raise ValueError("backfill aliases cannot contain blank symbols")
        key = (snapshot_symbol, session)
        if key in aliases:
            raise ValueError(f"duplicate backfill alias: {key}")
        aliases[key] = nse_symbol
    return aliases


def _default_nse_symbol(snapshot_symbol: str) -> str:
    clean = str(snapshot_symbol).strip().upper()
    if clean.endswith(".NS"):
        clean = clean[:-3]
    if not clean:
        raise ValueError("snapshot symbol cannot be blank")
    return clean


def nse_symbol_for_backfill(
    snapshot_symbol: str,
    session: date,
    *,
    aliases: dict[tuple[str, date], str],
) -> str:
    clean = str(snapshot_symbol).strip().upper()
    return aliases.get((clean, session), _default_nse_symbol(clean))


def _validate_baseline_bundle(
    input_snapshot_dir: Path,
) -> DailyAuditInputBundle:
    actual_sha = daily_audit_input_manifest_sha256(input_snapshot_dir)
    if actual_sha != EXPECTED_BASELINE_MANIFEST_SHA256:
        raise ValueError(
            "baseline manifest SHA mismatch: "
            f"expected={EXPECTED_BASELINE_MANIFEST_SHA256}, actual={actual_sha}"
        )
    bundle = load_daily_audit_input_bundle(input_snapshot_dir)
    if bundle.symbol_count != 30:
        raise ValueError("session-clean v2 expects the frozen 30-symbol basket")
    return bundle


def _source_row(
    bhavcopy: pd.DataFrame,
    *,
    session: date,
    nse_symbol: str,
) -> pd.Series:
    mask = (
        (bhavcopy["session"].dt.date == session)
        & (bhavcopy["nse_symbol"] == nse_symbol)
        & (bhavcopy["series"] == "EQ")
    )
    rows = bhavcopy.loc[mask]
    if len(rows) != 1:
        raise ValueError(
            "expected exactly one official EQ bhavcopy row for "
            f"{nse_symbol} on {session.isoformat()}, found {len(rows)}"
        )
    return rows.iloc[0]


def _calibration_scales(
    daily: pd.DataFrame,
    bhavcopy: pd.DataFrame,
    *,
    backfill_session: date,
    snapshot_symbol: str,
    nse_symbol: str,
    aliases: dict[tuple[str, date], str],
) -> tuple[float, float, pd.Series, date]:
    calibration_session = _BACKFILL_CALIBRATION_SESSION.get(backfill_session)
    if calibration_session is None:
        raise ValueError(
            "missing calibration-session contract for "
            f"{backfill_session.isoformat()}"
        )

    calibration_ts = pd.Timestamp(calibration_session)
    if calibration_ts not in daily.index:
        raise ValueError(
            "frozen source is missing calibration session "
            f"{snapshot_symbol} {calibration_session.isoformat()}"
        )

    calibration_symbol = nse_symbol_for_backfill(
        snapshot_symbol,
        calibration_session,
        aliases=aliases,
    )
    if calibration_symbol != nse_symbol:
        raise ValueError(
            "backfill/calibration NSE symbol mismatch for "
            f"{snapshot_symbol}: {nse_symbol} vs {calibration_symbol}"
        )

    official = _source_row(
        bhavcopy,
        session=calibration_session,
        nse_symbol=calibration_symbol,
    )
    frozen = daily.loc[calibration_ts]

    price_ratios = [
        float(frozen[column]) / float(official[column])
        for column in ("open", "high", "low", "close")
    ]
    if any(not math.isfinite(value) or value <= 0.0 for value in price_ratios):
        raise ValueError(
            "invalid price calibration ratio for "
            f"{snapshot_symbol} {calibration_session.isoformat()}"
        )
    price_scale = float(median(price_ratios))

    for column in ("open", "high", "low", "close"):
        expected = float(official[column]) * price_scale
        observed = float(frozen[column])
        if not math.isclose(
            expected,
            observed,
            rel_tol=5e-4,
            abs_tol=0.11,
        ):
            raise ValueError(
                "official calibration OHLC does not reconcile to frozen source: "
                f"symbol={snapshot_symbol}, session={calibration_session.isoformat()}, "
                f"column={column}, expected={expected}, observed={observed}, "
                f"price_scale={price_scale}"
            )

    official_volume = float(official["volume"])
    frozen_volume = float(frozen["volume"])
    if official_volume <= 0.0 or frozen_volume <= 0.0:
        raise ValueError(
            "calibration session requires positive official and frozen volume: "
            f"{snapshot_symbol} {calibration_session.isoformat()}"
        )
    volume_scale = frozen_volume / official_volume
    if not math.isfinite(volume_scale) or volume_scale <= 0.0:
        raise ValueError(
            "invalid volume calibration ratio for "
            f"{snapshot_symbol} {calibration_session.isoformat()}"
        )

    return price_scale, volume_scale, official, calibration_session


def _adjacent_scale_guard(
    daily: pd.DataFrame,
    *,
    session: date,
    backfill_close: float,
) -> None:
    earlier = daily.loc[daily.index < pd.Timestamp(session)]
    later = daily.loc[daily.index > pd.Timestamp(session)]
    anchors: list[float] = []
    if not earlier.empty:
        anchors.append(float(earlier.iloc[-1]["close"]))
    if not later.empty:
        anchors.append(float(later.iloc[0]["close"]))

    for anchor in anchors:
        ratio = backfill_close / anchor
        if not 0.25 <= ratio <= 4.0:
            raise ValueError(
                "official backfill failed adjacent-price scale guard: "
                f"session={session.isoformat()}, backfill={backfill_close}, "
                f"anchor={anchor}, ratio={ratio}"
            )


def repair_symbol_daily(
    *,
    symbol: str,
    daily: pd.DataFrame,
    reference: pd.DataFrame,
    bhavcopy: pd.DataFrame,
    aliases: dict[tuple[str, date], str],
) -> tuple[pd.DataFrame, tuple[SessionRepairRecord, ...]]:
    """Return one repaired symbol history and exact repair provenance."""

    clean_symbol = str(symbol).strip().upper()
    if daily.empty or not isinstance(daily.index, pd.DatetimeIndex):
        raise ValueError("baseline daily source must be non-empty DatetimeIndex")
    missing_columns = sorted(set(_REQUIRED_DAILY_COLUMNS) - set(daily.columns))
    if missing_columns:
        raise ValueError(f"baseline daily source missing columns: {missing_columns}")

    repaired = daily.copy().sort_index()
    if repaired.index.has_duplicates:
        raise ValueError("baseline daily source contains duplicate sessions")
    records: list[SessionRepairRecord] = []

    applicable = reference.loc[
        (reference["session"] >= repaired.index.min().normalize())
        & (reference["session"] <= repaired.index.max().normalize())
    ]

    for item in applicable.itertuples(index=False):
        session_ts = pd.Timestamp(item.session).normalize()
        session = session_ts.date()
        expected = str(item.expected_session)
        source_ref = str(item.source_ref)

        if expected == "closed":
            if session_ts not in repaired.index:
                continue
            row = repaired.loc[session_ts]
            if not (
                float(row["open"]) == float(row["high"])
                == float(row["low"])
                == float(row["close"])
                and float(row["volume"]) == 0.0
            ):
                raise ValueError(
                    "refusing to delete non-placeholder row on closed session: "
                    f"{clean_symbol} {session.isoformat()}"
                )
            records.append(
                SessionRepairRecord(
                    symbol=clean_symbol,
                    session=session.isoformat(),
                    action="REMOVE_CLOSED_SESSION_PLACEHOLDER",
                    nse_symbol=nse_symbol_for_backfill(
                        clean_symbol,
                        session,
                        aliases=aliases,
                    ),
                    source_path="",
                    source_sha256="",
                    source_ref=source_ref,
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )
            repaired = repaired.drop(session_ts)
            continue

        if expected != "open":
            raise ValueError(f"unsupported expected_session: {expected}")

        if session_ts in repaired.index:
            row = repaired.loc[session_ts]
            if float(row["volume"]) <= 0.0:
                raise ValueError(
                    "existing special-session row is not a positive-volume bar: "
                    f"{clean_symbol} {session.isoformat()}"
                )
            continue

        nse_symbol = nse_symbol_for_backfill(
            clean_symbol,
            session,
            aliases=aliases,
        )
        source = _source_row(
            bhavcopy,
            session=session,
            nse_symbol=nse_symbol,
        )
        if float(source["volume"]) <= 0.0:
            raise ValueError(
                "official special-session backfill must have positive volume: "
                f"{nse_symbol} {session.isoformat()}"
            )

        (
            price_scale,
            volume_scale,
            calibration_source,
            calibration_session,
        ) = _calibration_scales(
            repaired,
            bhavcopy,
            backfill_session=session,
            snapshot_symbol=clean_symbol,
            nse_symbol=nse_symbol,
            aliases=aliases,
        )
        scaled_open = float(source["open"]) * price_scale
        scaled_high = float(source["high"]) * price_scale
        scaled_low = float(source["low"]) * price_scale
        scaled_close = float(source["close"]) * price_scale
        scaled_volume = float(source["volume"]) * volume_scale

        _adjacent_scale_guard(
            repaired,
            session=session,
            backfill_close=scaled_close,
        )

        repaired.loc[session_ts, list(_REQUIRED_DAILY_COLUMNS)] = [
            scaled_open,
            scaled_high,
            scaled_low,
            scaled_close,
            scaled_volume,
        ]
        records.append(
            SessionRepairRecord(
                symbol=clean_symbol,
                session=session.isoformat(),
                action="ADD_OFFICIAL_SPECIAL_SESSION",
                nse_symbol=nse_symbol,
                source_path=str(source["source_path"]),
                source_sha256=str(source["source_sha256"]),
                source_ref=source_ref,
                open=scaled_open,
                high=scaled_high,
                low=scaled_low,
                close=scaled_close,
                volume=scaled_volume,
                calibration_session=calibration_session.isoformat(),
                calibration_source_path=str(calibration_source["source_path"]),
                calibration_source_sha256=str(
                    calibration_source["source_sha256"]
                ),
                price_scale=price_scale,
                volume_scale=volume_scale,
            )
        )

    repaired = repaired.sort_index()
    if repaired.index.has_duplicates:
        raise ValueError("repaired daily source contains duplicate sessions")
    return repaired, tuple(records)


def _manifest_payload(
    *,
    baseline_bundle: DailyAuditInputBundle,
    fingerprints: tuple[DailyAuditInputFingerprint, ...],
    source_records: tuple[OfficialBhavcopySource, ...],
    reference_path: Path,
    reference_sha256: str,
    repair_records: tuple[SessionRepairRecord, ...],
) -> dict[str, object]:
    removed = sum(
        item.action == "REMOVE_CLOSED_SESSION_PLACEHOLDER"
        for item in repair_records
    )
    added = sum(
        item.action == "ADD_OFFICIAL_SPECIAL_SESSION"
        for item in repair_records
    )
    return {
        "audit_id": DAILY_AUDIT_INPUT_SNAPSHOT_ID,
        "basket_name": baseline_bundle.basket_name + "_nse_session_clean_v2",
        "provider": "hybrid:yfinance-baseline+nse-official-bhavcopy",
        "period": baseline_bundle.period + "+nse-session-clean-v2",
        "cutoff": baseline_bundle.cutoff,
        "symbol_count": len(fingerprints),
        "is_actionable": False,
        "fingerprints": [asdict(item) for item in fingerprints],
        "repair": {
            "version": NSE_SESSION_CLEAN_SNAPSHOT_VERSION,
            "baseline_manifest_sha256": EXPECTED_BASELINE_MANIFEST_SHA256,
            "reference_path": str(reference_path),
            "reference_sha256": reference_sha256,
            "removed_row_count": removed,
            "added_row_count": added,
            "net_row_change": added - removed,
            "official_source_files": [asdict(item) for item in source_records],
            "production_calendar_change_authorized": False,
            "downstream_rerun_authorized": False,
        },
    }


def build_nse_session_clean_snapshot(
    *,
    input_snapshot_dir: str | Path,
    official_bhavcopy_paths: Sequence[str | Path],
    output_dir: str | Path,
    reference_path: str | Path = DEFAULT_REFERENCE_PATH,
    alias_path: str | Path = DEFAULT_ALIAS_PATH,
    overwrite: bool = False,
) -> SessionCleanSnapshotBuild:
    """Create a new immutable session-clean snapshot without mutating baseline."""

    input_root = Path(input_snapshot_dir)
    output_root = Path(output_dir)
    manifest_json = output_root / "daily_audit_input_manifest.json"
    manifest_csv = output_root / "daily_audit_input_manifest.csv"
    repairs_csv = output_root / "nse_session_clean_repairs.csv"
    source_files_csv = output_root / "nse_session_clean_source_files.csv"

    if manifest_json.exists() and not overwrite:
        raise FileExistsError(
            f"session-clean output already exists: {manifest_json}"
        )

    baseline_bundle = _validate_baseline_bundle(input_root)
    reference_path_obj = Path(reference_path)
    reference = load_nse_session_exception_reference(reference_path_obj)
    reference_sha = sha256(reference_path_obj.read_bytes()).hexdigest()
    aliases = load_backfill_aliases(alias_path)
    bhavcopy, source_records = load_official_bhavcopy_sources(
        official_bhavcopy_paths
    )

    expected_missing_sessions = {
        pd.Timestamp(value).date()
        for value in reference.loc[
            reference["expected_session"] == "open", "session"
        ]
    }
    supplied_sessions = {
        pd.Timestamp(value).date()
        for value in bhavcopy["session"]
    }
    # 2025-02-01 is already present in the frozen source and therefore does not
    # need a backfill. Every genuinely missing special session also requires one
    # immediately preceding normal-session bhavcopy so official raw OHLCV can be
    # transformed onto the frozen provider's corporate-action-restated basis.
    required_backfill_sessions = expected_missing_sessions - {date(2025, 2, 1)}
    required_source_sessions = required_backfill_sessions | set(
        _BACKFILL_CALIBRATION_SESSION.values()
    )
    missing_sources = sorted(required_source_sessions - supplied_sessions)
    unexpected_sources = sorted(supplied_sessions - required_source_sessions)
    if missing_sources or unexpected_sources:
        raise ValueError(
            "official bhavcopy session set mismatch: "
            f"missing={[d.isoformat() for d in missing_sources]}, "
            f"unexpected={[d.isoformat() for d in unexpected_sources]}"
        )

    snapshots_dir = output_root / "snapshots"
    output_root.mkdir(parents=True, exist_ok=True)
    snapshots_dir.mkdir(parents=True, exist_ok=True)

    output_period = baseline_bundle.period + "+nse-session-clean-v2"
    fingerprints: list[DailyAuditInputFingerprint] = []
    all_repairs: list[SessionRepairRecord] = []

    for baseline_fp in baseline_bundle.fingerprints:
        daily = load_daily_audit_input(input_root, baseline_fp.symbol)
        repaired, repairs = repair_symbol_daily(
            symbol=baseline_fp.symbol,
            daily=daily,
            reference=reference,
            bhavcopy=bhavcopy,
            aliases=aliases,
        )

        removed = sum(
            item.action == "REMOVE_CLOSED_SESSION_PLACEHOLDER"
            for item in repairs
        )
        added = sum(
            item.action == "ADD_OFFICIAL_SPECIAL_SESSION"
            for item in repairs
        )
        if removed != 4 or added != 5:
            raise ValueError(
                "unexpected per-symbol repair count for "
                f"{baseline_fp.symbol}: removed={removed}, added={added}"
            )
        if len(repaired) != len(daily) + 1:
            raise ValueError(
                f"{baseline_fp.symbol}: repaired row count must equal baseline + 1"
            )

        relative_path = f"snapshots/{baseline_fp.symbol}.csv"
        snapshot_path = output_root / relative_path
        repaired.reset_index().to_csv(
            snapshot_path,
            index=False,
            float_format="%.17g",
        )

        reloaded = pd.read_csv(
            snapshot_path,
            parse_dates=["session"],
            float_precision="round_trip",
        ).set_index("session")
        reloaded.index.name = "session"
        fingerprint = fingerprint_daily_audit_input(
            baseline_fp.symbol,
            reloaded,
            period=output_period,
            cutoff=baseline_bundle.cutoff,
            relative_path=relative_path,
        )
        fingerprints.append(fingerprint)
        all_repairs.extend(repairs)

    repair_records = tuple(all_repairs)
    if len(repair_records) != 270:
        raise ValueError(
            f"expected 270 total repair records, found {len(repair_records)}"
        )

    fingerprints_tuple = tuple(fingerprints)
    payload = _manifest_payload(
        baseline_bundle=baseline_bundle,
        fingerprints=fingerprints_tuple,
        source_records=source_records,
        reference_path=reference_path_obj,
        reference_sha256=reference_sha,
        repair_records=repair_records,
    )
    manifest_json.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    pd.DataFrame([asdict(item) for item in fingerprints_tuple]).to_csv(
        manifest_csv,
        index=False,
    )
    pd.DataFrame([asdict(item) for item in repair_records]).to_csv(
        repairs_csv,
        index=False,
    )
    pd.DataFrame([asdict(item) for item in source_records]).to_csv(
        source_files_csv,
        index=False,
    )

    output_manifest_sha = sha256(manifest_json.read_bytes()).hexdigest()
    return SessionCleanSnapshotBuild(
        output_dir=output_root,
        manifest_json=manifest_json,
        manifest_csv=manifest_csv,
        repairs_csv=repairs_csv,
        source_files_csv=source_files_csv,
        baseline_manifest_sha256=EXPECTED_BASELINE_MANIFEST_SHA256,
        output_manifest_sha256=output_manifest_sha,
        symbol_count=len(fingerprints_tuple),
        removed_row_count=sum(
            item.action == "REMOVE_CLOSED_SESSION_PLACEHOLDER"
            for item in repair_records
        ),
        added_row_count=sum(
            item.action == "ADD_OFFICIAL_SPECIAL_SESSION"
            for item in repair_records
        ),
    )


__all__ = [
    "DEFAULT_ALIAS_PATH",
    "EXPECTED_BASELINE_MANIFEST_SHA256",
    "NSE_SESSION_CLEAN_SNAPSHOT_VERSION",
    "OfficialBhavcopySource",
    "SessionCleanSnapshotBuild",
    "SessionRepairRecord",
    "build_nse_session_clean_snapshot",
    "load_backfill_aliases",
    "load_official_bhavcopy_sources",
    "normalize_official_bhavcopy_frame",
    "nse_symbol_for_backfill",
    "repair_symbol_daily",
]
