from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from data import completed_weekly_only
import api.service as service_module
from api.service import ProVSAService


def _daily_frame(start: str, periods: int) -> pd.DataFrame:
    index = pd.bdate_range(start=start, periods=periods)
    return pd.DataFrame(
        {
            "open": range(100, 100 + periods),
            "high": range(101, 101 + periods),
            "low": range(99, 99 + periods),
            "close": range(100, 100 + periods),
            "volume": range(1000, 1000 + periods),
        },
        index=index,
    )


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
        reason="No actionable candidate.",
        signal_bar_anomaly=False,
        signal_bar_anomaly_reason=None,
        bar_index=0,
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


def test_api_analysis_uses_only_completed_weekly_bars(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeMetricsEngine:
        def calculate(self, weekly: pd.DataFrame) -> pd.DataFrame:
            captured["weekly"] = weekly.copy()
            return weekly

    def fake_scan_latest_candidate_production(
        metrics: pd.DataFrame,
        *,
        symbol: str,
        timeframe: str,
        state_store,
        state_root,
        allow_full_replay_fallback: bool,
    ):
        captured["metrics"] = metrics.copy()
        captured["target_index"] = len(metrics) - 1
        captured["symbol"] = symbol
        captured["timeframe"] = timeframe
        captured["allow_full_replay_fallback"] = allow_full_replay_fallback
        return _fake_candidate()

    monkeypatch.setattr(service_module, "download_data", lambda symbol: _daily_frame("2026-08-31", 6))
    monkeypatch.setattr(
        service_module,
        "completed_weekly_only",
        lambda weekly: completed_weekly_only(weekly, now="2026-09-07 10:00"),
    )
    monkeypatch.setattr(service_module, "MetricsEngine", lambda: FakeMetricsEngine())
    monkeypatch.setattr(
        service_module,
        "scan_latest_candidate_production",
        fake_scan_latest_candidate_production,
    )

    result = ProVSAService(persist_decision_context=False).analyze_symbol(" test.ns ")

    weekly = captured["weekly"]
    assert isinstance(weekly, pd.DataFrame)
    assert list(weekly["week_beginning"]) == [pd.Timestamp("2026-08-31")]
    assert captured["target_index"] == 0
    assert captured["symbol"] == "TEST.NS"
    assert captured["timeframe"] == "1W"
    assert captured["allow_full_replay_fallback"] is True
    assert result.symbol == "TEST.NS"
    assert result.latest_bar_index == 0
    assert result.latest_week == "2026-08-31 00:00:00"
    assert [bar.week for bar in result.bars] == ["2026-08-31 00:00:00"]
