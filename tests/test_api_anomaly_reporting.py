from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from decision_context import DecisionContextStore
from engine.columns import (
    COL_CORPORATE_ACTION_ANOMALY,
    COL_PRICE_ANOMALY,
    COL_PRICE_GAP_RATIO,
    COL_VOLUME_ANOMALY,
)
import api.service as service_module
from api.service import ProVSAService


def _weekly_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "week_beginning": pd.to_datetime(["2026-08-24", "2026-08-31"]),
            "open": [100.0, 150.0],
            "high": [110.0, 151.0],
            "low": [95.0, 149.0],
            "close": [108.0, 150.5],
            "volume": [1_000_000.0, 7_500_000.0],
        }
    )


def _metrics_frame() -> pd.DataFrame:
    metrics = _weekly_frame().copy()
    metrics[COL_PRICE_GAP_RATIO] = [None, 0.40]
    metrics[COL_PRICE_ANOMALY] = [False, True]
    metrics[COL_VOLUME_ANOMALY] = [False, True]
    metrics[COL_CORPORATE_ACTION_ANOMALY] = [False, True]
    return metrics


def _fake_candidate() -> SimpleNamespace:
    trend = SimpleNamespace(
        direction=SimpleNamespace(value="SIDEWAYS"),
        state=SimpleNamespace(value="UNKNOWN"),
        strength=0.0,
        confidence=0.0,
        swing_count=0,
        hh_count=0,
        hl_count=0,
        lh_count=0,
        ll_count=0,
        swings=(),
        structural_swings=(),
    )
    return SimpleNamespace(
        evidence=SimpleNamespace(
            context=SimpleNamespace(trend=trend),
            evidence=(),
        ),
        qualification=SimpleNamespace(value="UNQUALIFIED"),
        qualification_result=SimpleNamespace(
            evidence_codes=(),
            evidence_bar_indices=(),
        ),
        actionable=False,
        reason="Signal bar has a corporate-action anomaly flag.",
        signal_bar_anomaly=True,
        signal_bar_anomaly_reason="Signal bar has a corporate-action anomaly flag.",
        bar_index=1,
        week="2026-08-31 00:00:00",
        execution_pending=False,
        professional=SimpleNamespace(
            trend=0.0,
            supply=0.0,
            demand=0.0,
            effort=0.0,
            strength=0.0,
            weakness=0.0,
            confidence=0.0,
        ),
        net_strength=0.0,
        net_pressure=0.0,
        confidence=0.0,
    )


def test_api_analysis_reports_bar_signal_and_decision_context_metadata(
    monkeypatch,
    tmp_path,
) -> None:
    class FakeMetricsEngine:
        def calculate(self, weekly: pd.DataFrame) -> pd.DataFrame:
            assert list(weekly["week_beginning"]) == list(_weekly_frame()["week_beginning"])
            return _metrics_frame()

    class FakeScannerEngine:
        def scan_to_index(self, metrics: pd.DataFrame, target_index: int):
            assert target_index == 1
            assert bool(metrics.iloc[target_index][COL_CORPORATE_ACTION_ANOMALY])
            return _fake_candidate()

    monkeypatch.setattr(service_module, "download_data", lambda symbol: pd.DataFrame())
    monkeypatch.setattr(service_module, "daily_to_weekly", lambda daily: _weekly_frame())
    monkeypatch.setattr(service_module, "completed_weekly_only", lambda weekly: weekly)
    monkeypatch.setattr(service_module, "MetricsEngine", lambda: FakeMetricsEngine())
    monkeypatch.setattr(service_module, "ScannerEngine", lambda: FakeScannerEngine())

    store = DecisionContextStore(tmp_path)
    result = ProVSAService(decision_context_store=store).analyze_symbol(" test.ns ")

    assert result.symbol == "TEST.NS"
    assert result.anomaly_bar_indices == [1]
    assert result.signal_bar_anomaly is True
    assert result.signal_bar_anomaly_reason == "Signal bar has a corporate-action anomaly flag."

    assert result.bars[0].price_gap_ratio is None
    assert result.bars[0].corporate_action_anomaly is False

    anomaly_bar = result.bars[1]
    assert anomaly_bar.price_gap_ratio == 0.40
    assert anomaly_bar.price_anomaly is True
    assert anomaly_bar.volume_anomaly is True
    assert anomaly_bar.corporate_action_anomaly is True

    assert result.decision_context is not None
    assert result.decision_context.symbol == "TEST.NS"
    assert result.decision_context.timeframe == "1W"
    assert result.decision_context.mode == "confirmed"
    assert result.decision_context.tradability == "avoid"
    assert result.decision_context.decision == "avoid"
    assert result.decision_context.latest_bar_index == 1
    assert result.decision_context.story.what_to_expect_next

    loaded = store.load("TEST.NS", "1W")
    assert loaded.to_dict() == result.decision_context.dict()


def test_api_anomaly_helpers_default_safely_when_columns_are_missing() -> None:
    row = _weekly_frame().iloc[0]

    assert ProVSAService._optional_float(row, COL_PRICE_GAP_RATIO) is None
    assert ProVSAService._bool_flag(row, COL_CORPORATE_ACTION_ANOMALY) is False
    assert ProVSAService._anomaly_bar_indices(_weekly_frame()) == []