from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd

from audit.genuine_daily_sequence_case import (
    ProductionWeeklySourceFingerprint,
)
from audit.weekly_progression_score_input_audit import (
    WEEKLY_PROGRESSION_SCORE_INPUT_AUDIT_ID,
    audit_weekly_progression_score_inputs,
    write_weekly_progression_score_input_audit,
)
from models import EvidenceCode


def _fingerprint() -> ProductionWeeklySourceFingerprint:
    return ProductionWeeklySourceFingerprint(
        symbol="LT.NS",
        row_count=10,
        first_week="2026-01-02T00:00:00",
        last_week="2026-03-06T00:00:00",
        sha256="sha256:test-weekly",
    )


def _struct_score(value: float):
    return SimpleNamespace(
        price=value,
        structural_size=value,
        duration=value,
        volume=value,
        spread=value,
        overall=value,
    )


def _smart_score(value: float):
    return SimpleNamespace(
        stopping_volume=value,
        climactic_volume=value,
        overall=value,
    )


def _swing(
    *,
    confirmation: int,
    professional: float,
    structure: float,
    smart_money: float,
):
    history = SimpleNamespace(
        current_amplitude=10.0 + confirmation,
        current_duration=3,
        current_spread_adjusted_amplitude=8.0 + confirmation,
        amplitudes=(1.0, 2.0),
        volumes=(1.0, 2.0),
        spreads=(1.0, 2.0),
    )
    professional_score = SimpleNamespace(
        structure=_struct_score(structure),
        smart_money=_smart_score(smart_money),
        overall=professional,
    )
    return SimpleNamespace(
        swing=SimpleNamespace(
            confirmation_index=confirmation,
            bar_index=confirmation - 2,
            type=SimpleNamespace(value="low"),
            week_beginning=f"W{confirmation}",
            label=None,
        ),
        grade=SimpleNamespace(name="MINOR"),
        is_failed=False,
        evaluation=SimpleNamespace(
            professional=professional_score,
            structure=SimpleNamespace(snapshot=history),
        ),
    )


def _event(code: EvidenceCode, bar_index: int):
    return SimpleNamespace(
        code=code,
        bar_index=bar_index,
        week_beginning=f"W{bar_index}",
    )


def _candidate(swings, event=None):
    target = () if event is None else (event,)
    return SimpleNamespace(
        target_bar_evidence=target,
        evidence=SimpleNamespace(
            context=SimpleNamespace(
                structural_swings=tuple(swings),
            )
        ),
    )


def test_audit_reconstructs_exact_progression_window_delta() -> None:
    swings = tuple(
        _swing(
            confirmation=index,
            professional=value,
            structure=value,
            smart_money=value,
        )
        for index, value in enumerate(
            (0.2, 0.3, 0.4, 0.6, 0.7, 0.8),
            start=10,
        )
    )
    event = _event(
        EvidenceCode.STRUCTURAL_PROGRESSION_IMPROVING,
        15,
    )
    audit = audit_weekly_progression_score_inputs(
        symbol="lt.ns",
        candidates=(_candidate(swings, event),),
        source_fingerprint=_fingerprint(),
    )

    assert audit.symbol == "LT.NS"
    assert audit.audit_id == WEEKLY_PROGRESSION_SCORE_INPUT_AUDIT_ID
    assert audit.unique_structural_swing_count == 6
    assert audit.progression_event_count == 1
    row = audit.window_rows[0]
    assert row.event_direction == "bullish"
    assert row.window_size == 3
    assert row.reconstruction_matches is True
    assert row.reported_progression_difference > 0
    assert row.professional_overall_delta > 0


def test_component_deltas_show_structural_and_smart_money_contributions() -> None:
    swings = (
        _swing(confirmation=10, professional=0.8, structure=0.9, smart_money=0.4),
        _swing(confirmation=11, professional=0.8, structure=0.9, smart_money=0.4),
        _swing(confirmation=12, professional=0.8, structure=0.9, smart_money=0.4),
        _swing(confirmation=13, professional=0.4, structure=0.4, smart_money=0.4),
        _swing(confirmation=14, professional=0.4, structure=0.4, smart_money=0.4),
        _swing(confirmation=15, professional=0.4, structure=0.4, smart_money=0.4),
    )
    event = _event(
        EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
        15,
    )
    audit = audit_weekly_progression_score_inputs(
        symbol="LT.NS",
        candidates=(_candidate(swings, event),),
        source_fingerprint=_fingerprint(),
    )

    row = audit.window_rows[0]
    assert row.professional_overall_delta < 0
    assert row.structure_overall_delta < 0
    assert row.smart_money_overall_delta == 0


def test_unique_swing_ledger_deduplicates_replayed_candidate_context() -> None:
    early = tuple(
        _swing(
            confirmation=index,
            professional=0.5,
            structure=0.5,
            smart_money=0.5,
        )
        for index in range(10, 16)
    )
    later = early + (
        _swing(
            confirmation=16,
            professional=0.4,
            structure=0.4,
            smart_money=0.4,
        ),
    )
    audit = audit_weekly_progression_score_inputs(
        symbol="LT.NS",
        candidates=(
            _candidate(early),
            _candidate(later),
        ),
        source_fingerprint=_fingerprint(),
    )

    assert audit.unique_structural_swing_count == 7
    assert len(audit.swing_rows) == 7


def test_writer_outputs_summary_and_two_ledgers(tmp_path) -> None:
    swings = tuple(
        _swing(
            confirmation=index,
            professional=value,
            structure=value,
            smart_money=value,
        )
        for index, value in enumerate(
            (0.8, 0.8, 0.8, 0.4, 0.4, 0.4),
            start=10,
        )
    )
    event = _event(
        EvidenceCode.STRUCTURAL_PROGRESSION_WEAKENING,
        15,
    )
    audit = audit_weekly_progression_score_inputs(
        symbol="LT.NS",
        candidates=(_candidate(swings, event),),
        source_fingerprint=_fingerprint(),
    )

    paths = write_weekly_progression_score_input_audit(
        audit,
        tmp_path,
    )
    summary = json.loads(paths.summary_json.read_text(encoding="utf-8"))
    swing_ledger = pd.read_csv(paths.swing_ledger_csv)
    window_ledger = pd.read_csv(paths.progression_window_csv)

    assert summary["progression_event_count"] == 1
    assert summary["event_direction_counts"] == {
        "bearish": 1,
        "bullish": 0,
    }
    assert summary["is_actionable"] is False
    assert len(swing_ledger) == 6
    assert len(window_ledger) == 1
    assert bool(window_ledger.loc[0, "reconstruction_matches"]) is True
