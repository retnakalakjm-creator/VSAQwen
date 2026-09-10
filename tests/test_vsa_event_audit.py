from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from vsa_event_audit import (
    AUDIT_FLAG_BULLISH_VSA_AGAINST_BEARISH_QUALIFICATION,
    AUDIT_FLAG_FALLBACK_SCORING_EVIDENCE,
    AUDIT_FLAG_NO_TARGET_EVENT,
    AUDIT_FLAG_QUALIFICATION_WITHOUT_CURRENT_EVIDENCE,
    AUDIT_FLAG_STALE_SCORING_EVIDENCE,
    AUDIT_FLAG_STRUCTURAL_EVENT_WITHOUT_VSA_CONFIRMATION,
    DETECTOR_DIAGNOSTIC_HIGH_VOLUME_REVERSAL_WITHOUT_BULLISH_EVENT,
    DETECTOR_DIAGNOSTIC_POTENTIAL_ABSORPTION,
    DETECTOR_DIAGNOSTIC_POTENTIAL_EFFORT_GT_RESULT,
    DETECTOR_DIAGNOSTIC_POTENTIAL_STOPPING_VOLUME,
    build_vsa_event_audit,
    parse_symbol_list,
)


def _weekly_frame(rows: int = 36) -> pd.DataFrame:
    weeks = pd.date_range("2026-01-05", periods=rows, freq="W-MON")
    records = []
    for index, week in enumerate(weeks):
        open_ = 100.0 + index
        close = open_ + (2.0 if index % 3 else -1.5)
        high = max(open_, close) + 2.0
        low = min(open_, close) - 2.0
        records.append(
            {
                "week_beginning": week,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": 1_000_000.0 + index * 20_000.0,
            }
        )
    return pd.DataFrame(records)


def _high_volume_reversal_frame(rows: int = 36) -> pd.DataFrame:
    weekly = _weekly_frame(rows)
    weekly["volume"] = 1_000_000.0
    weekly.loc[21, "close"] = 119.0
    weekly.loc[22, ["open", "high", "low", "close", "volume"]] = [
        120.0,
        122.0,
        112.0,
        118.0,
        3_000_000.0,
    ]
    return weekly


def _event(code: str) -> SimpleNamespace:
    return SimpleNamespace(code=code)


def _candidate(
    index: int,
    week: str,
    target_events=(),
    *,
    scoring_events=None,
    qualifying_events=None,
    campaign_events=None,
    qualification: str = "unqualified",
    actionable: bool = False,
    used_fallback_evidence: bool | None = None,
    scoring_evidence_age: int | None = None,
):
    if scoring_events is None:
        scoring_events = target_events or (_event("stopping_volume"),)
    if qualifying_events is None:
        qualifying_events = ()
    if campaign_events is None:
        campaign_events = target_events
    if used_fallback_evidence is None:
        used_fallback_evidence = not bool(target_events)
    if scoring_evidence_age is None and not target_events:
        scoring_evidence_age = 2
    return SimpleNamespace(
        bar_index=index,
        week=week,
        target_bar_evidence=target_events,
        scoring_evidence=scoring_events,
        qualifying_evidence=qualifying_events,
        campaign_evidence=campaign_events,
        qualification=SimpleNamespace(value=qualification),
        actionable=actionable,
        used_fallback_evidence=used_fallback_evidence,
        scoring_evidence_age=scoring_evidence_age,
        net_pressure=0.25,
        confidence=0.55,
        signal_bar_anomaly=False,
        signal_bar_anomaly_reason=None,
    )


class FakeScanner:
    def __init__(self) -> None:
        self.scan_lengths: list[int] = []

    def scan(self, metrics: pd.DataFrame):
        self.scan_lengths.append(len(metrics))
        candidates = []
        for index in range(20, len(metrics)):
            week = str(metrics.iloc[index]["week_beginning"])
            if index == 22:
                candidates.append(
                    _candidate(index, week, (_event("stopping_volume"),), actionable=True)
                )
            elif index == 23:
                candidates.append(
                    _candidate(index, week, (_event("structural_progression_weakening"),))
                )
            else:
                candidates.append(_candidate(index, week, ()))
        return candidates


class FlagScanner:
    def scan(self, metrics: pd.DataFrame):
        candidates = []
        for index in range(20, len(metrics)):
            week = str(metrics.iloc[index]["week_beginning"])
            if index == 21:
                candidates.append(
                    _candidate(
                        index,
                        week,
                        (),
                        scoring_events=(_event("increasing_supply"),),
                        campaign_events=(_event("increasing_supply"),),
                        qualification="persistent_bearish",
                        used_fallback_evidence=True,
                        scoring_evidence_age=5,
                    )
                )
            elif index == 22:
                candidates.append(
                    _candidate(
                        index,
                        week,
                        (_event("structural_progression_weakening"),),
                        qualifying_events=(_event("structural_progression_weakening"),),
                        qualification="persistent_bearish",
                    )
                )
            elif index == 23:
                candidates.append(
                    _candidate(
                        index,
                        week,
                        (_event("demand_coming_in"),),
                        qualifying_events=(_event("structural_progression_weakening"),),
                        qualification="persistent_bearish",
                    )
                )
            elif index == 24:
                candidates.append(
                    _candidate(
                        index,
                        week,
                        (),
                        scoring_events=(),
                        campaign_events=(),
                        qualifying_events=(_event("structural_progression_weakening"),),
                        qualification="persistent_bearish",
                        used_fallback_evidence=False,
                        scoring_evidence_age=None,
                    )
                )
            else:
                candidates.append(_candidate(index, week, ()))
        return candidates


class DiagnosticScanner:
    def __init__(self, target_code: str = "increasing_supply") -> None:
        self._target_code = target_code

    def scan(self, metrics: pd.DataFrame):
        candidates = []
        for index in range(20, len(metrics)):
            week = str(metrics.iloc[index]["week_beginning"])
            if index == 22:
                target = (_event(self._target_code),)
                candidates.append(
                    _candidate(
                        index,
                        week,
                        target,
                        scoring_events=(_event("increasing_supply"),),
                        campaign_events=(_event("increasing_supply"),),
                        qualification="persistent_bearish",
                    )
                )
            else:
                candidates.append(_candidate(index, week, ()))
        return candidates


def test_parse_symbol_list_deduplicates_and_limits_symbols() -> None:
    assert parse_symbol_list("lt.ns, SRF.NS;lt.ns") == ["LT.NS", "SRF.NS"]

    with pytest.raises(ValueError, match="max_symbols"):
        parse_symbol_list("A.NS,B.NS,C.NS", max_symbols=2)


def test_build_vsa_event_audit_runs_one_bounded_scan_and_returns_compact_rows() -> None:
    weekly = _weekly_frame()
    scanner = FakeScanner()
    start_week = str(weekly.iloc[22]["week_beginning"])

    audit = build_vsa_event_audit(
        symbol="LT.NS",
        weekly=weekly,
        start_week=start_week,
        horizon_weeks=2,
        scanner=scanner,
    )

    assert scanner.scan_lengths == [24]
    assert audit.symbol == "LT.NS"
    assert audit.timeframe == "1W"
    assert audit.replay_weeks == 2
    assert len(audit.rows) == 2

    first, second = audit.rows
    assert first.replay_bar_index == 22
    assert first.target_event_codes == ("stopping_volume",)
    assert first.vsa_event_codes == ("stopping_volume",)
    assert first.structural_event_codes == ()
    assert first.actionable is True
    assert first.event_count == 1

    assert second.replay_bar_index == 23
    assert second.target_event_codes == ("structural_progression_weakening",)
    assert second.structural_event_codes == ("structural_progression_weakening",)
    assert second.vsa_event_codes == ()
    assert AUDIT_FLAG_STRUCTURAL_EVENT_WITHOUT_VSA_CONFIRMATION in second.audit_flags


def test_audit_flags_surface_review_cases_without_changing_scanner_behavior() -> None:
    weekly = _weekly_frame()

    audit = build_vsa_event_audit(
        symbol="LT.NS",
        weekly=weekly,
        start_week=str(weekly.iloc[21]["week_beginning"]),
        horizon_weeks=4,
        scanner=FlagScanner(),
    )

    stale, structural_only, demand_against_bearish, old_qualification = audit.rows

    assert stale.audit_flags == (
        AUDIT_FLAG_NO_TARGET_EVENT,
        AUDIT_FLAG_FALLBACK_SCORING_EVIDENCE,
        AUDIT_FLAG_STALE_SCORING_EVIDENCE,
    )
    assert structural_only.audit_flags == (
        AUDIT_FLAG_STRUCTURAL_EVENT_WITHOUT_VSA_CONFIRMATION,
    )
    assert demand_against_bearish.audit_flags == (
        AUDIT_FLAG_BULLISH_VSA_AGAINST_BEARISH_QUALIFICATION,
    )
    assert old_qualification.audit_flags == (
        AUDIT_FLAG_NO_TARGET_EVENT,
        AUDIT_FLAG_QUALIFICATION_WITHOUT_CURRENT_EVIDENCE,
    )
    assert "audit_flags" in demand_against_bearish.to_dict()


def test_detector_diagnostics_surface_high_volume_reversal_review_cases() -> None:
    weekly = _high_volume_reversal_frame()

    audit = build_vsa_event_audit(
        symbol="LT.NS",
        weekly=weekly,
        start_week=str(weekly.iloc[22]["week_beginning"]),
        horizon_weeks=1,
        scanner=DiagnosticScanner(),
    )

    row = audit.rows[0]
    assert row.target_event_codes == ("increasing_supply",)
    assert row.detector_diagnostics == (
        DETECTOR_DIAGNOSTIC_POTENTIAL_STOPPING_VOLUME,
        DETECTOR_DIAGNOSTIC_POTENTIAL_EFFORT_GT_RESULT,
        DETECTOR_DIAGNOSTIC_POTENTIAL_ABSORPTION,
        DETECTOR_DIAGNOSTIC_HIGH_VOLUME_REVERSAL_WITHOUT_BULLISH_EVENT,
    )
    assert "detector_diagnostics" in row.to_dict()
    assert any("Effort vs Result" in note for note in row.notes)


def test_detector_diagnostics_do_not_duplicate_expected_fired_event() -> None:
    weekly = _high_volume_reversal_frame()

    audit = build_vsa_event_audit(
        symbol="LT.NS",
        weekly=weekly,
        start_week=str(weekly.iloc[22]["week_beginning"]),
        horizon_weeks=1,
        scanner=DiagnosticScanner(target_code="stopping_volume"),
    )

    row = audit.rows[0]
    assert row.target_event_codes == ("stopping_volume",)
    assert DETECTOR_DIAGNOSTIC_POTENTIAL_STOPPING_VOLUME not in row.detector_diagnostics
    assert (
        DETECTOR_DIAGNOSTIC_HIGH_VOLUME_REVERSAL_WITHOUT_BULLISH_EVENT
        not in row.detector_diagnostics
    )


def test_build_vsa_event_audit_rejects_oversized_replay_window() -> None:
    weekly = _weekly_frame()

    with pytest.raises(ValueError, match="requested audit window"):
        build_vsa_event_audit(
            symbol="LT.NS",
            weekly=weekly,
            start_week=str(weekly.iloc[21]["week_beginning"]),
            end_week=str(weekly.iloc[30]["week_beginning"]),
            max_replay_weeks=2,
            scanner=FakeScanner(),
        )
