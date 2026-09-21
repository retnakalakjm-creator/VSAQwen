from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

import audit.daily_event_inventory_runner as runner
from audit.daily_input_reproducibility import (
    DailyAuditInputBundle,
    DailyAuditInputFingerprint,
    build_daily_audit_input_bundle,
)


def _fingerprint(
    symbol: str,
    *,
    row_count: int,
) -> DailyAuditInputFingerprint:
    return DailyAuditInputFingerprint(
        symbol=symbol,
        version="daily-ohlcv-v1",
        period="max",
        cutoff="2026-09-18T00:00:00",
        row_count=row_count,
        first_session="2020-01-01T00:00:00",
        last_session="2026-09-18T00:00:00",
        sha256=(symbol[0].lower() * 64),
        relative_path=f"snapshots/{symbol}.csv",
    )


def _bundle() -> DailyAuditInputBundle:
    return DailyAuditInputBundle(
        audit_id="daily-audit-input-snapshot-v1",
        basket_name="test-basket",
        provider="fixture",
        period="max",
        cutoff="2026-09-18T00:00:00",
        symbol_count=3,
        fingerprints=(
            _fingerprint("A.NS", row_count=10),
            _fingerprint("B.NS", row_count=30),
            _fingerprint("C.NS", row_count=20),
        ),
    )


def test_default_worker_count_is_conservative(monkeypatch) -> None:
    monkeypatch.setattr(runner.os, "cpu_count", lambda: 8)
    assert runner.default_snapshot_worker_count(30) == 4

    monkeypatch.setattr(runner.os, "cpu_count", lambda: 3)
    assert runner.default_snapshot_worker_count(30) == 2

    monkeypatch.setattr(runner.os, "cpu_count", lambda: 1)
    assert runner.default_snapshot_worker_count(30) == 1


def test_longest_first_scheduling_restores_requested_order(
    monkeypatch,
    tmp_path,
) -> None:
    seen: list[str] = []
    progress: list[str] = []

    def fake_task(task):
        symbol = task[0]
        seen.append(symbol)
        archive = SimpleNamespace(
            symbol=symbol,
            evaluated_bar_count=100,
        )
        return runner._SnapshotWorkerCompletion(
            symbol=symbol,
            archive=archive,
        )

    monkeypatch.setattr(runner, "_snapshot_worker_task", fake_task)

    result = runner.run_frozen_snapshot_replay(
        ("A.NS", "B.NS", "C.NS"),
        bundle=_bundle(),
        input_snapshot_dir=tmp_path,
        now="2026-09-18T16:00:00+05:30",
        min_target_index=20,
        workers=1,
        progress_writer=progress.append,
    )

    assert seen == ["B.NS", "C.NS", "A.NS"]
    assert tuple(item.symbol for item in result.archives) == (
        "A.NS",
        "B.NS",
        "C.NS",
    )
    assert result.failures == ()
    assert result.worker_count == 1
    assert progress[0].endswith("3 symbols, 1 workers")
    assert "1/3 completed B.NS" in progress[1]


class _FakeProvider:
    name = "fixture"

    def download_daily(
        self,
        symbol: str,
        *,
        period: str,
        interval: str,
        auto_adjust: bool,
    ) -> pd.DataFrame:
        del symbol, period, interval, auto_adjust
        return pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [102.0, 103.0],
                "Low": [99.0, 100.0],
                "Close": [101.0, 102.0],
                "Volume": [1000.0, 1100.0],
            },
            index=pd.to_datetime(
                ["2026-09-17", "2026-09-18"]
            ),
        )


def test_spawned_parallel_replay_reads_verified_snapshots(
    tmp_path,
) -> None:
    bundle, _ = build_daily_audit_input_bundle(
        ("A.NS", "B.NS"),
        basket_name="test-basket",
        cutoff="2026-09-18",
        output_dir=tmp_path,
        provider=_FakeProvider(),
    )

    result = runner.run_frozen_snapshot_replay(
        ("A.NS", "B.NS"),
        bundle=bundle,
        input_snapshot_dir=tmp_path,
        now="2026-09-19T16:00:00+05:30",
        min_target_index=20,
        workers=2,
    )

    assert result.worker_count == 2
    assert result.failures == ()
    assert tuple(item.symbol for item in result.archives) == (
        "A.NS",
        "B.NS",
    )
    assert all(item.evaluated_bar_count == 0 for item in result.archives)
