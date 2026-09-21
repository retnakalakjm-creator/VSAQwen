from __future__ import annotations

import pandas as pd

from audit.daily_event_confirmation_runner import (
    default_confirmation_worker_count,
    run_frozen_confirmation_replay,
)
from audit.daily_input_reproducibility import (
    build_daily_audit_input_bundle,
)


class _FixtureProvider:
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
        index = pd.to_datetime(["2026-01-01", "2026-01-02"])
        return pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [102.0, 103.0],
                "Low": [99.0, 100.0],
                "Close": [101.0, 102.0],
                "Volume": [1000.0, 1100.0],
            },
            index=index,
        )


def test_default_confirmation_worker_count_is_conservative(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        "audit.daily_event_confirmation_runner.os.cpu_count",
        lambda: 16,
    )
    assert default_confirmation_worker_count(30) == 4

    monkeypatch.setattr(
        "audit.daily_event_confirmation_runner.os.cpu_count",
        lambda: 2,
    )
    assert default_confirmation_worker_count(30) == 1


def test_spawned_frozen_confirmation_replay_uses_verified_snapshots(
    tmp_path,
) -> None:
    symbols = ("AAA.NS", "BBB.NS")
    bundle, _ = build_daily_audit_input_bundle(
        symbols,
        basket_name="test-basket",
        cutoff="2026-01-02",
        output_dir=tmp_path,
        provider=_FixtureProvider(),
    )
    progress: list[str] = []

    result = run_frozen_confirmation_replay(
        symbols,
        bundle=bundle,
        input_snapshot_dir=tmp_path,
        now="2026-01-02T16:00:00+05:30",
        min_target_index=20,
        workers=2,
        progress_writer=progress.append,
    )

    assert result.worker_count == 2
    assert result.failures == ()
    assert result.observations == ()
    assert progress[0] == (
        "[daily-confirmation] frozen replay: 2 symbols, 2 workers"
    )
    assert len(progress) == 3
