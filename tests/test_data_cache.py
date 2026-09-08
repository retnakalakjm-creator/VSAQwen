from __future__ import annotations

import os
import time

import pandas as pd
import pytest

import data


def _daily_frame(rows: int = 5) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=rows, freq="D", name="date")
    return pd.DataFrame(
        {
            "open": [100.0 + i for i in range(rows)],
            "high": [101.0 + i for i in range(rows)],
            "low": [99.0 + i for i in range(rows)],
            "close": [100.5 + i for i in range(rows)],
            "volume": [1_000 + i for i in range(rows)],
        },
        index=index,
    )


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(data, "MIN_DAILY_BARS", 1)


def test_write_cached_data_creates_cache_and_metadata() -> None:
    expected = _daily_frame()

    cache_path = data._write_cached_data("TEST.NS", expected, source="unit_test")

    assert cache_path.exists()
    assert data._cache_metadata_path("TEST.NS").exists()

    if data._parquet_engine_available():
        actual = data._read_parquet_cache("TEST.NS")
        expected_format = "parquet"
    else:
        actual = data._read_legacy_csv_cache("TEST.NS")
        expected_format = "csv"

    pd.testing.assert_frame_equal(
        actual,
        expected,
        check_freq=False,
    )

    metadata = data.read_cache_metadata("TEST.NS")
    assert metadata is not None
    assert metadata.format == expected_format
    assert metadata.source == "unit_test"
    assert metadata.rows == len(expected)
    assert metadata.first_date == pd.Timestamp(expected.index[0]).isoformat()
    assert metadata.last_date == pd.Timestamp(expected.index[-1]).isoformat()
    assert metadata.stale_reason is None


def test_write_cached_data_uses_csv_when_parquet_engine_is_unavailable(monkeypatch) -> None:
    expected = _daily_frame()
    monkeypatch.setattr(data, "_parquet_engine_available", lambda: False)

    cache_path = data._write_cached_data("TEST.NS", expected, source="unit_test")

    assert cache_path == data._legacy_cache_path("TEST.NS")
    assert cache_path.exists()
    assert not data._cache_data_path("TEST.NS").exists()

    actual = data._read_legacy_csv_cache("TEST.NS")
    pd.testing.assert_frame_equal(
            actual,
            expected,
            check_freq=False,
    )

    metadata = data.read_cache_metadata("TEST.NS")
    assert metadata is not None
    assert metadata.format == "csv"
    assert metadata.source == "unit_test"


def test_download_data_migrates_legacy_csv_cache_when_parquet_is_available(monkeypatch) -> None:
    if not data._parquet_engine_available():
        pytest.skip("Parquet migration requires pyarrow or fastparquet")

    expected = _daily_frame()
    legacy_path = data._legacy_cache_path("TEST.NS")
    expected.to_csv(legacy_path)

    def fail_download(*args, **kwargs):
        raise AssertionError("fresh legacy cache should not download")

    monkeypatch.setattr(data.yf, "download", fail_download)

    actual = data.download_data("TEST.NS", cache_max_age=60 * 60)

    pd.testing.assert_frame_equal(
            actual,
            expected,
            check_freq=False,
    )
    assert data._cache_data_path("TEST.NS").exists()

    metadata = data.read_cache_metadata("TEST.NS")
    assert metadata is not None
    assert metadata.source == "csv_migration"
    assert metadata.format == "parquet"


def test_download_data_keeps_legacy_csv_cache_when_parquet_is_unavailable(monkeypatch) -> None:
    expected = _daily_frame()
    legacy_path = data._legacy_cache_path("TEST.NS")
    expected.to_csv(legacy_path)
    monkeypatch.setattr(data, "_parquet_engine_available", lambda: False)

    def fail_download(*args, **kwargs):
        raise AssertionError("fresh legacy cache should not download")

    monkeypatch.setattr(data.yf, "download", fail_download)

    actual = data.download_data("TEST.NS", cache_max_age=60 * 60)

    pd.testing.assert_frame_equal(
           actual,
           expected,
           check_freq=False,
    )
    assert legacy_path.exists()
    assert not data._cache_data_path("TEST.NS").exists()


def test_download_data_refreshes_stale_cache(monkeypatch) -> None:
    cached = _daily_frame(3)
    refreshed = _daily_frame(5)
    data._write_cached_data("TEST.NS", cached, source="unit_test")

    def fake_download(*args, **kwargs):
        return pd.DataFrame(
            {
                "Open": refreshed["open"],
                "High": refreshed["high"],
                "Low": refreshed["low"],
                "Close": refreshed["close"],
                "Volume": refreshed["volume"],
            }
        )

    monkeypatch.setattr(data.yf, "download", fake_download)

    actual = data.download_data("TEST.NS", cache_max_age=0)

    # pd.testing.assert_frame_equal(actual, refreshed)
    pd.testing.assert_frame_equal(
            actual,
            refreshed,
            check_freq=False,
        )
    metadata = data.read_cache_metadata("TEST.NS")
    assert metadata is not None
    assert metadata.source == "incremental_refresh"
    assert metadata.rows == len(refreshed)


def test_download_data_returns_stale_cache_and_records_reason(monkeypatch) -> None:
    cached = _daily_frame()
    data._write_cached_data("TEST.NS", cached, source="unit_test")

    def fail_download(*args, **kwargs):
        raise RuntimeError("network unavailable")

    monkeypatch.setattr(data.yf, "download", fail_download)

    actual = data.download_data("TEST.NS", cache_max_age=0)

    pd.testing.assert_frame_equal(
            actual,
            cached,
            check_freq=False,
    )
    metadata = data.read_cache_metadata("TEST.NS")
    assert metadata is not None
    assert metadata.source == "stale_cache"
    assert metadata.stale_reason == "network unavailable"


def test_download_data_uses_fresh_cache_without_network(monkeypatch) -> None:
    expected = _daily_frame()
    cache_path = data._write_cached_data("TEST.NS", expected, source="unit_test")
    os.utime(cache_path, (time.time(), time.time()))

    def fail_download(*args, **kwargs):
        raise AssertionError("fresh cache should not download")

    monkeypatch.setattr(data.yf, "download", fail_download)

    actual = data.download_data("TEST.NS", cache_max_age=60 * 60)
    
    pd.testing.assert_frame_equal(
            actual,
            expected,
            check_freq=False,
    )

