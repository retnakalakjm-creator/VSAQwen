from __future__ import annotations

import pandas as pd
import pytest

import data


class _AuditProvider:
    name = "audit-provider"

    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.calls: list[dict[str, object]] = []

    def download_daily(
        self,
        symbol: str,
        *,
        period: str,
        interval: str,
        auto_adjust: bool,
    ) -> pd.DataFrame:
        self.calls.append(
            {
                "symbol": symbol,
                "period": period,
                "interval": interval,
                "auto_adjust": auto_adjust,
            }
        )
        return self.frame.copy()


def _canonical_frame(rows: int = 30) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=rows, freq="D", name="date")
    return pd.DataFrame(
        {
            "open": [100.0 + index for index in range(rows)],
            "high": [101.0 + index for index in range(rows)],
            "low": [99.0 + index for index in range(rows)],
            "close": [100.5 + index for index in range(rows)],
            "volume": [1_000_000.0 + index for index in range(rows)],
        },
        index=dates,
    )


def _provider_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        }
    )


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(data, "MIN_DAILY_BARS", 1)
    monkeypatch.setattr(data, "_parquet_engine_available", lambda: False)


def test_history_revision_audit_skips_network_when_no_cache() -> None:
    provider = _AuditProvider(_provider_frame(_canonical_frame()))

    result = data.audit_cached_history_revision("TEST.NS", provider=provider)

    assert result.status == "NO_CACHE"
    assert result.revision_detected is False
    assert provider.calls == []


def test_history_revision_audit_treats_append_only_bars_as_match() -> None:
    cached = _canonical_frame(25)
    downloaded = _canonical_frame(30)
    data._write_cached_data("TEST.NS", cached, source="unit_test")
    provider = _AuditProvider(_provider_frame(downloaded))

    result = data.audit_cached_history_revision("TEST.NS", provider=provider)

    assert result.status == "MATCH"
    assert result.revision_detected is False
    assert result.changed_rows == 0
    assert result.changed_columns == ()
    assert result.overlap_rows == len(cached)
    assert result.provider_newer_rows == 5
    assert provider.calls == [
        {
            "symbol": "TEST.NS",
            "period": data.DEFAULT_PERIOD,
            "interval": data.CACHE_INTERVAL,
            "auto_adjust": False,
        }
    ]


def test_history_revision_audit_detects_old_revision_outside_incremental_window() -> None:
    cached = _canonical_frame(30)
    downloaded = cached.copy()
    changed_date = downloaded.index[4]
    downloaded.loc[changed_date, "open"] += 12.0
    downloaded.loc[changed_date, "high"] += 12.0
    downloaded.loc[changed_date, "low"] += 12.0
    downloaded.loc[changed_date, "close"] += 12.0
    downloaded.loc[changed_date, "volume"] *= 2.0

    cache_path = data._write_cached_data("TEST.NS", cached, source="unit_test")
    generation_before = data.inspect_cache_generation("TEST.NS")
    provider = _AuditProvider(_provider_frame(downloaded))

    result = data.audit_cached_history_revision("TEST.NS", provider=provider)

    assert result.status == "REVISION_DETECTED"
    assert result.revision_detected is True
    assert result.changed_rows == 1
    assert result.changed_columns == ("close", "high", "low", "open", "volume")
    assert result.earliest_changed_date == changed_date.isoformat()
    assert result.latest_changed_date == changed_date.isoformat()
    assert result.cached_only_dates == 0
    assert result.provider_only_dates == 0

    # Audit is read-only: it must not repair or rewrite the cache implicitly.
    pd.testing.assert_frame_equal(
        data._read_legacy_csv_cache("TEST.NS"),
        cached,
        check_freq=False,
    )
    generation_after = data.inspect_cache_generation("TEST.NS")
    assert generation_after.actual_generation == generation_before.actual_generation
    assert cache_path.exists()


def test_history_revision_audit_detects_historical_date_identity_change() -> None:
    cached = _canonical_frame(30)
    downloaded = cached.drop(index=cached.index[8])
    data._write_cached_data("TEST.NS", cached, source="unit_test")
    provider = _AuditProvider(_provider_frame(downloaded))

    result = data.audit_cached_history_revision("TEST.NS", provider=provider)

    assert result.status == "REVISION_DETECTED"
    assert result.changed_rows == 1
    assert result.changed_columns == ("__date_identity__",)
    assert result.cached_only_dates == 1
    assert result.provider_only_dates == 0


def test_history_revision_compare_uses_small_numeric_tolerance() -> None:
    cached = _canonical_frame(30)
    downloaded = cached.copy()
    downloaded.loc[downloaded.index[10], "close"] += 1e-11

    result = data.compare_cached_history_revision(
        "TEST.NS",
        cached,
        downloaded,
        provider_name="unit",
    )

    assert result.status == "MATCH"
    assert result.changed_rows == 0
