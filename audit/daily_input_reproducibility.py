"""Reproducible full-history daily OHLCV snapshots for research audits.

This module is audit-only. It bypasses the mutable production cache and downloads
an explicit full-history period, truncates it to a fixed cutoff session, writes
normalized CSV snapshots, and records deterministic SHA-256 fingerprints.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from config import AUTO_ADJUST, DEFAULT_INTERVAL, FULL_HISTORY_PERIOD
from data import DEFAULT_DATA_PROVIDER
from market_data import MarketDataProvider


DAILY_AUDIT_INPUT_SNAPSHOT_ID = "daily-audit-input-snapshot-v1"
DAILY_INPUT_FINGERPRINT_VERSION = "daily-ohlcv-v1"
_FINGERPRINT_COLUMNS = (
    "session",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


@dataclass(frozen=True, slots=True)
class DailyAuditInputFingerprint:
    symbol: str
    version: str
    period: str
    cutoff: str
    row_count: int
    first_session: str | None
    last_session: str | None
    sha256: str
    relative_path: str
    columns: tuple[str, ...] = _FINGERPRINT_COLUMNS


@dataclass(frozen=True, slots=True)
class DailyAuditInputBundle:
    audit_id: str
    basket_name: str
    provider: str
    period: str
    cutoff: str
    symbol_count: int
    fingerprints: tuple[DailyAuditInputFingerprint, ...]

    @property
    def is_actionable(self) -> bool:
        return False


@dataclass(frozen=True, slots=True)
class DailyAuditInputBundlePaths:
    manifest_json: Path
    manifest_csv: Path
    snapshots_dir: Path

    def as_dict(self) -> dict[str, str]:
        return {
            "manifest_json": str(self.manifest_json),
            "manifest_csv": str(self.manifest_csv),
            "snapshots_dir": str(self.snapshots_dir),
        }


def _normalize_symbol(symbol: str) -> str:
    normalized = str(symbol).strip().upper()
    if not normalized:
        raise ValueError("symbol cannot be blank")
    return normalized


def _normalize_cutoff(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("cutoff cannot be missing")
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp.normalize()


def _session_text(value: object) -> str:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("daily input contains a missing session")
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_localize(None)
    return timestamp.normalize().isoformat()


def _number_text(value: object) -> str:
    number = float(value)
    if math.isnan(number):
        return "nan"
    if math.isinf(number):
        return "+inf" if number > 0 else "-inf"
    return number.hex()


def _normalize_downloaded_daily(
    frame: pd.DataFrame,
    *,
    cutoff: object,
) -> pd.DataFrame:
    if frame.empty:
        raise ValueError("No data returned")

    normalized = frame.copy()
    if isinstance(normalized.columns, pd.MultiIndex):
        normalized.columns = normalized.columns.get_level_values(0)

    required = ["Open", "High", "Low", "Close", "Volume"]
    missing = [column for column in required if column not in normalized.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    normalized = normalized.loc[:, required].copy()
    normalized.columns = ["open", "high", "low", "close", "volume"]

    index = pd.DatetimeIndex(pd.to_datetime(normalized.index))
    if index.tz is not None:
        index = index.tz_localize(None)
    normalized.index = index.normalize()
    normalized.index.name = "session"
    normalized.sort_index(inplace=True)
    if normalized.index.has_duplicates:
        raise ValueError("daily audit input requires unique sessions")

    normalized = normalized.loc[
        normalized.index <= _normalize_cutoff(cutoff)
    ].copy()
    if normalized.empty:
        raise ValueError("No data remains at or before cutoff")
    if normalized.isna().any().any():
        raise ValueError("daily audit input contains missing values")
    return normalized


def _snapshot_frame(frame: pd.DataFrame) -> pd.DataFrame:
    snapshot = frame.reset_index()
    return snapshot.loc[:, list(_FINGERPRINT_COLUMNS)]


def fingerprint_daily_audit_input(
    symbol: str,
    daily: pd.DataFrame,
    *,
    period: str,
    cutoff: object,
    relative_path: str,
) -> DailyAuditInputFingerprint:
    normalized_symbol = _normalize_symbol(symbol)
    cutoff_text = _normalize_cutoff(cutoff).isoformat()
    snapshot = _snapshot_frame(daily)

    digest = sha256()
    digest.update(f"{DAILY_INPUT_FINGERPRINT_VERSION}\n".encode("utf-8"))
    digest.update(f"{period}\n".encode("utf-8"))
    digest.update(f"{cutoff_text}\n".encode("utf-8"))
    digest.update(("|".join(_FINGERPRINT_COLUMNS) + "\n").encode("utf-8"))

    first_session: str | None = None
    last_session: str | None = None
    for values in snapshot.itertuples(index=False, name=None):
        session = _session_text(values[0])
        if first_session is None:
            first_session = session
        last_session = session
        encoded = [session, *(_number_text(value) for value in values[1:])]
        digest.update(("|".join(encoded) + "\n").encode("utf-8"))

    return DailyAuditInputFingerprint(
        symbol=normalized_symbol,
        version=DAILY_INPUT_FINGERPRINT_VERSION,
        period=str(period),
        cutoff=cutoff_text,
        row_count=len(snapshot),
        first_session=first_session,
        last_session=last_session,
        sha256=digest.hexdigest(),
        relative_path=relative_path,
    )


def _manifest_payload(bundle: DailyAuditInputBundle) -> dict[str, object]:
    return {
        "audit_id": bundle.audit_id,
        "basket_name": bundle.basket_name,
        "provider": bundle.provider,
        "period": bundle.period,
        "cutoff": bundle.cutoff,
        "symbol_count": bundle.symbol_count,
        "is_actionable": False,
        "fingerprints": [asdict(item) for item in bundle.fingerprints],
    }


def _read_manifest(root: Path) -> dict[str, object]:
    manifest_path = root / "daily_audit_input_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if payload.get("audit_id") != DAILY_AUDIT_INPUT_SNAPSHOT_ID:
        raise ValueError("unexpected daily audit input audit_id")
    if payload.get("is_actionable") is not False:
        raise ValueError("daily audit input bundle must remain non-actionable")
    return payload


def daily_audit_input_manifest_sha256(
    input_dir: str | Path,
) -> str:
    manifest_path = Path(input_dir) / "daily_audit_input_manifest.json"
    return sha256(manifest_path.read_bytes()).hexdigest()


def load_daily_audit_input_bundle(
    input_dir: str | Path,
) -> DailyAuditInputBundle:
    root = Path(input_dir)
    payload = _read_manifest(root)
    raw_fingerprints = payload.get("fingerprints")
    if not isinstance(raw_fingerprints, list):
        raise ValueError("daily audit input manifest missing fingerprints")

    fingerprints: list[DailyAuditInputFingerprint] = []
    for item in raw_fingerprints:
        if not isinstance(item, dict):
            raise ValueError("daily audit input fingerprint must be an object")
        fingerprints.append(
            DailyAuditInputFingerprint(
                symbol=_normalize_symbol(str(item["symbol"])),
                version=str(item["version"]),
                period=str(item["period"]),
                cutoff=str(item["cutoff"]),
                row_count=int(item["row_count"]),
                first_session=(
                    None
                    if item.get("first_session") is None
                    else str(item["first_session"])
                ),
                last_session=(
                    None
                    if item.get("last_session") is None
                    else str(item["last_session"])
                ),
                sha256=str(item["sha256"]),
                relative_path=str(item["relative_path"]),
                columns=tuple(str(value) for value in item["columns"]),
            )
        )

    symbol_count = int(payload["symbol_count"])
    if symbol_count != len(fingerprints):
        raise ValueError(
            "daily audit input symbol_count does not match fingerprints"
        )

    symbols = tuple(item.symbol for item in fingerprints)
    if len(set(symbols)) != len(symbols):
        raise ValueError("daily audit input manifest symbols must be unique")
    paths = tuple(item.relative_path for item in fingerprints)
    if len(set(paths)) != len(paths):
        raise ValueError(
            "daily audit input snapshot paths must be unique"
        )

    period = str(payload["period"])
    cutoff = str(payload["cutoff"])
    if any(item.period != period for item in fingerprints):
        raise ValueError("daily audit input period mismatch")
    if any(item.cutoff != cutoff for item in fingerprints):
        raise ValueError("daily audit input cutoff mismatch")

    return DailyAuditInputBundle(
        audit_id=str(payload["audit_id"]),
        basket_name=str(payload["basket_name"]),
        provider=str(payload["provider"]),
        period=period,
        cutoff=cutoff,
        symbol_count=symbol_count,
        fingerprints=tuple(fingerprints),
    )


def build_daily_audit_input_bundle(
    symbols: Sequence[str] | Iterable[str],
    *,
    basket_name: str,
    cutoff: object,
    output_dir: str | Path,
    provider: MarketDataProvider = DEFAULT_DATA_PROVIDER,
    period: str = FULL_HISTORY_PERIOD,
    overwrite: bool = False,
) -> tuple[DailyAuditInputBundle, DailyAuditInputBundlePaths]:
    normalized_symbols = tuple(_normalize_symbol(symbol) for symbol in symbols)
    if not normalized_symbols:
        raise ValueError("at least one symbol is required")
    if len(set(normalized_symbols)) != len(normalized_symbols):
        raise ValueError("symbols must be unique")

    root = Path(output_dir)
    manifest_path = root / "daily_audit_input_manifest.json"
    if manifest_path.exists() and not overwrite:
        raise FileExistsError(
            f"daily audit input manifest already exists: {manifest_path}"
        )
    snapshots_dir = root / "snapshots"
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    cutoff_text = _normalize_cutoff(cutoff).isoformat()
    provider_name = str(getattr(provider, "name", type(provider).__name__))

    fingerprints: list[DailyAuditInputFingerprint] = []
    for symbol in normalized_symbols:
        downloaded = provider.download_daily(
            symbol,
            period=period,
            interval=DEFAULT_INTERVAL,
            auto_adjust=AUTO_ADJUST,
        )
        daily = _normalize_downloaded_daily(downloaded, cutoff=cutoff)
        relative_path = f"snapshots/{symbol}.csv"
        snapshot_path = root / relative_path
        _snapshot_frame(daily).to_csv(
            snapshot_path,
            index=False,
            float_format="%.17g",
        )

        reloaded = pd.read_csv(
            snapshot_path,
            parse_dates=["session"],
            float_precision="round_trip",
        )
        reloaded = reloaded.set_index("session")
        reloaded.index.name = "session"
        fingerprint = fingerprint_daily_audit_input(
            symbol,
            reloaded,
            period=period,
            cutoff=cutoff,
            relative_path=relative_path,
        )
        fingerprints.append(fingerprint)

    bundle = DailyAuditInputBundle(
        audit_id=DAILY_AUDIT_INPUT_SNAPSHOT_ID,
        basket_name=str(basket_name),
        provider=provider_name,
        period=str(period),
        cutoff=cutoff_text,
        symbol_count=len(fingerprints),
        fingerprints=tuple(fingerprints),
    )
    paths = DailyAuditInputBundlePaths(
        manifest_json=manifest_path,
        manifest_csv=root / "daily_audit_input_manifest.csv",
        snapshots_dir=snapshots_dir,
    )
    paths.manifest_json.write_text(
        json.dumps(_manifest_payload(bundle), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    pd.DataFrame([asdict(item) for item in bundle.fingerprints]).to_csv(
        paths.manifest_csv,
        index=False,
    )
    return bundle, paths


def load_daily_audit_input(
    input_dir: str | Path,
    symbol: str,
) -> pd.DataFrame:
    root = Path(input_dir)
    normalized_symbol = _normalize_symbol(symbol)
    bundle = load_daily_audit_input_bundle(root)
    matches = [
        item
        for item in bundle.fingerprints
        if item.symbol == normalized_symbol
    ]
    if len(matches) != 1:
        raise ValueError(
            f"expected exactly one manifest row for {normalized_symbol}"
        )
    record = matches[0]
    snapshot_path = root / record.relative_path
    frame = pd.read_csv(
        snapshot_path,
        parse_dates=["session"],
        float_precision="round_trip",
    )
    frame = frame.set_index("session")
    frame.index.name = "session"

    actual = fingerprint_daily_audit_input(
        normalized_symbol,
        frame,
        period=record.period,
        cutoff=record.cutoff,
        relative_path=record.relative_path,
    )
    expected_fields = (
        "version",
        "period",
        "cutoff",
        "row_count",
        "first_session",
        "last_session",
        "sha256",
        "relative_path",
    )
    mismatches = [
        field
        for field in expected_fields
        if getattr(actual, field) != getattr(record, field)
    ]
    expected_columns = record.columns
    if actual.columns != expected_columns:
        mismatches.append("columns")
    if mismatches:
        raise ValueError(
            f"daily audit input fingerprint mismatch for {normalized_symbol}: "
            f"{sorted(set(mismatches))}"
        )
    return frame


__all__ = [
    "DAILY_AUDIT_INPUT_SNAPSHOT_ID",
    "DAILY_INPUT_FINGERPRINT_VERSION",
    "DailyAuditInputBundle",
    "DailyAuditInputBundlePaths",
    "DailyAuditInputFingerprint",
    "build_daily_audit_input_bundle",
    "daily_audit_input_manifest_sha256",
    "fingerprint_daily_audit_input",
    "load_daily_audit_input",
    "load_daily_audit_input_bundle",
]
