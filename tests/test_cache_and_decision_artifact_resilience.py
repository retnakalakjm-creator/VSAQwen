from __future__ import annotations

import json

import pandas as pd

import data
from api.service import ProVSAService
from decision_context import DecisionContextStore
from decision_journal import (
    DECISION_JOURNAL_SCHEMA_VERSION,
    DecisionJournalEntry,
    DecisionJournalStore,
    ValidationOutcome,
)


class _FakeMarketDataProvider:
    name = "fake"

    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.calls = 0

    def download_daily(
        self,
        symbol: str,
        *,
        period: str,
        interval: str,
        auto_adjust: bool,
    ) -> pd.DataFrame:
        self.calls += 1
        return self.frame.copy()


def _daily_frame(rows: int | None = None) -> pd.DataFrame:
    count = rows or data.MIN_DAILY_BARS
    dates = pd.date_range("2025-01-01", periods=count, freq="D")
    return pd.DataFrame(
        {
            "Open": [100.0 + index for index in range(count)],
            "High": [101.0 + index for index in range(count)],
            "Low": [99.0 + index for index in range(count)],
            "Close": [100.5 + index for index in range(count)],
            "Volume": [1_000_000.0 + index for index in range(count)],
        },
        index=dates,
    )


def _journal_entry(symbol: str = "TEST.NS") -> DecisionJournalEntry:
    return DecisionJournalEntry(
        schema_version=DECISION_JOURNAL_SCHEMA_VERSION,
        entry_id=f"{symbol}__1W__2026-09-04__42",
        symbol=symbol,
        timeframe="1W",
        source_context_week="2026-09-04",
        source_context_bar_index=42,
        source_context_evaluated_at_utc="2026-09-04T10:00:00+00:00",
        created_at_utc="2026-09-04T10:00:00+00:00",
        phase="uncertain",
        bias="neutral",
        tradability="observation_only",
        decision="observe_only",
        confidence=0.0,
        net_pressure=0.0,
        headline="No decisive VSA context yet",
        summary="Observation-only context.",
        confirmation_condition="Wait for directional evidence.",
        invalidation_condition="Conflicting evidence keeps the story unconfirmed.",
        expected_next_behavior=("Wait for clearer evidence.",),
        support_price=None,
        resistance_price=None,
        reference_price=None,
        status=ValidationOutcome.PENDING,
    )


def test_parquet_only_cache_rebuilds_csv_when_parquet_engine_unusable(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(data, "_parquet_engine_available", lambda: False)
    data._cache_data_path("TEST.NS").write_bytes(b"blocked parquet bytes")
    provider = _FakeMarketDataProvider(_daily_frame())

    loaded = data.download_data("TEST.NS", provider=provider)

    assert provider.calls == 1
    assert not loaded.empty
    assert data._legacy_cache_path("TEST.NS").exists()
    metadata = data.read_cache_metadata("TEST.NS")
    assert metadata is not None
    assert metadata.format == data.CACHE_FORMAT_CSV
    assert metadata.source == "historical_download"


def test_existing_csv_is_used_when_parquet_engine_is_unusable(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(data, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(data, "_parquet_engine_available", lambda: False)
    data._cache_data_path("TEST.NS").write_bytes(b"blocked parquet bytes")
    cached = _daily_frame().rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    )
    data._write_csv_cache("TEST.NS", cached, source="historical_download")
    provider = _FakeMarketDataProvider(_daily_frame())

    loaded = data.download_data(
        "TEST.NS",
        provider=provider,
        cache_max_age=60 * 60,
    )

    assert provider.calls == 0
    assert len(loaded) == len(cached)


def test_invalid_decision_journal_is_rebuilt_on_upsert(tmp_path) -> None:
    store = DecisionJournalStore(root=tmp_path)
    entry = _journal_entry()
    path = store.path_for(entry.symbol, entry.timeframe)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")

    store.upsert(entry)

    assert store.load_all(entry.symbol, entry.timeframe) == (entry,)


def test_invalid_decision_context_is_ignored_before_analysis_rebuild(tmp_path) -> None:
    store = DecisionContextStore(root=tmp_path)
    path = store.path_for("TEST.NS", "1W")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")
    service = ProVSAService(
        decision_context_store=store,
        persist_decision_context=False,
        persist_decision_journal=False,
    )

    assert service._load_cached_decision_context("TEST.NS") is None


def test_invalid_legacy_decision_journal_is_replaced_on_upsert(tmp_path) -> None:
    store = DecisionJournalStore(root=tmp_path)
    entry = _journal_entry("LEGACY.NS")
    legacy_payload = entry.to_dict()
    legacy_payload["schema_version"] = 0
    path = store.path_for(entry.symbol, entry.timeframe)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([legacy_payload]), encoding="utf-8")

    store.upsert(entry)

    assert store.load_all(entry.symbol, entry.timeframe) == (entry,)
