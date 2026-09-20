from __future__ import annotations

import json

import pandas as pd
import pytest

from audit.daily_input_reproducibility import (
    DAILY_AUDIT_INPUT_SNAPSHOT_ID,
    DAILY_INPUT_FINGERPRINT_VERSION,
    build_daily_audit_input_bundle,
    fingerprint_daily_audit_input,
    load_daily_audit_input,
)


class FakeProvider:
    name = "fake-provider"

    def __init__(self, frame: pd.DataFrame) -> None:
        self.frame = frame
        self.calls: list[tuple[str, str, str, bool]] = []

    def download_daily(
        self,
        symbol: str,
        *,
        period: str,
        interval: str,
        auto_adjust: bool,
    ) -> pd.DataFrame:
        self.calls.append((symbol, period, interval, auto_adjust))
        return self.frame.copy()


def _downloaded_daily() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [100.0, 101.0, 102.0, 103.0],
            "High": [104.0, 105.0, 106.0, 107.0],
            "Low": [99.0, 100.0, 101.0, 102.0],
            "Close": [103.0, 102.0, 105.0, 106.0],
            "Volume": [
                1_000_000.0,
                900_000.0,
                1_200_000.0,
                1_100_000.0,
            ],
        },
        index=pd.to_datetime(
            [
                "2020-01-02",
                "2021-01-04",
                "2026-09-18",
                "2026-09-21",
            ]
        ),
    )


def _normalized_daily() -> pd.DataFrame:
    frame = _downloaded_daily().iloc[:3].copy()
    frame.columns = ["open", "high", "low", "close", "volume"]
    frame.index.name = "session"
    return frame


def test_daily_input_fingerprint_is_deterministic() -> None:
    frame = _normalized_daily()

    first = fingerprint_daily_audit_input(
        "abc.ns",
        frame,
        period="max",
        cutoff="2026-09-18",
        relative_path="snapshots/ABC.NS.csv",
    )
    second = fingerprint_daily_audit_input(
        "ABC.NS",
        frame.copy(),
        period="max",
        cutoff="2026-09-18T00:00:00",
        relative_path="snapshots/ABC.NS.csv",
    )

    assert first == second
    assert first.symbol == "ABC.NS"
    assert first.version == DAILY_INPUT_FINGERPRINT_VERSION
    assert first.row_count == 3
    assert first.first_session == "2020-01-02T00:00:00"
    assert first.last_session == "2026-09-18T00:00:00"
    assert len(first.sha256) == 64


def test_daily_input_fingerprint_changes_with_ohlcv() -> None:
    original = _normalized_daily()
    changed = original.copy()
    changed.loc[pd.Timestamp("2021-01-04"), "close"] = 102.25

    original_hash = fingerprint_daily_audit_input(
        "ABC.NS",
        original,
        period="max",
        cutoff="2026-09-18",
        relative_path="snapshots/ABC.NS.csv",
    ).sha256
    changed_hash = fingerprint_daily_audit_input(
        "ABC.NS",
        changed,
        period="max",
        cutoff="2026-09-18",
        relative_path="snapshots/ABC.NS.csv",
    ).sha256

    assert original_hash != changed_hash


def test_builder_uses_full_history_provider_and_fixed_cutoff(
    tmp_path,
) -> None:
    provider = FakeProvider(_downloaded_daily())

    bundle, paths = build_daily_audit_input_bundle(
        ("abc.ns",),
        basket_name="test-basket",
        cutoff="2026-09-18",
        output_dir=tmp_path,
        provider=provider,
    )

    assert provider.calls == [("ABC.NS", "max", "1d", False)]
    assert bundle.audit_id == DAILY_AUDIT_INPUT_SNAPSHOT_ID
    assert bundle.provider == "fake-provider"
    assert bundle.period == "max"
    assert bundle.symbol_count == 1
    assert bundle.is_actionable is False
    assert bundle.fingerprints[0].row_count == 3
    assert (
        bundle.fingerprints[0].last_session
        == "2026-09-18T00:00:00"
    )

    loaded = load_daily_audit_input(tmp_path, "ABC.NS")
    assert len(loaded) == 3
    assert loaded.index[-1] == pd.Timestamp("2026-09-18")
    assert paths.manifest_json.exists()
    assert paths.manifest_csv.exists()
    assert (paths.snapshots_dir / "ABC.NS.csv").exists()

    payload = json.loads(
        paths.manifest_json.read_text(encoding="utf-8")
    )
    assert payload["period"] == "max"
    assert payload["cutoff"] == "2026-09-18T00:00:00"
    assert payload["is_actionable"] is False


def test_builder_refuses_silent_snapshot_overwrite(tmp_path) -> None:
    provider = FakeProvider(_downloaded_daily())

    build_daily_audit_input_bundle(
        ("ABC.NS",),
        basket_name="test-basket",
        cutoff="2026-09-18",
        output_dir=tmp_path,
        provider=provider,
    )

    with pytest.raises(FileExistsError):
        build_daily_audit_input_bundle(
            ("ABC.NS",),
            basket_name="test-basket",
            cutoff="2026-09-18",
            output_dir=tmp_path,
            provider=provider,
        )


def test_loader_rejects_tampered_snapshot(tmp_path) -> None:
    provider = FakeProvider(_downloaded_daily())
    build_daily_audit_input_bundle(
        ("ABC.NS",),
        basket_name="test-basket",
        cutoff="2026-09-18",
        output_dir=tmp_path,
        provider=provider,
    )

    snapshot = tmp_path / "snapshots" / "ABC.NS.csv"
    frame = pd.read_csv(snapshot)
    frame.loc[1, "close"] = 999.0
    frame.to_csv(snapshot, index=False, float_format="%.17g")

    with pytest.raises(ValueError, match="fingerprint mismatch"):
        load_daily_audit_input(tmp_path, "ABC.NS")
