"""Effort-vs-Result engine invocation preflight validation.

This test suite is intentionally a guardrail before enabling the production
EvidenceEngine effort hook. It validates the existing hook boundary and the
zero-weight contextual behavior that must survive any later invocation PR.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

from evidence.effort import collect_effort
from evidence.engine import EvidenceEngine
from evidence.weight import WeightCalculator
from models import (
    ClosePosition,
    EvidenceCategory,
    EvidenceCode,
    EvidenceDirection,
    SpreadClass,
    VolumeClass,
)


def _ctx(
    *,
    volume: VolumeClass = VolumeClass.VERY_HIGH,
    spread: SpreadClass = SpreadClass.NARROW,
    close: ClosePosition = ClosePosition.LOWER,
    bar_index: int = 7,
    week_beginning: str = "2026-03-02",
):
    current = SimpleNamespace(
        volume=volume,
        spread=spread,
        close_position=close,
        bar_index=bar_index,
        week_beginning=week_beginning,
    )
    return SimpleNamespace(current=current)


def _active_collect_effort_calls(source: str) -> list[str]:
    return [
        line.strip()
        for line in source.splitlines()
        if "self._collect_effort()" in line and not line.strip().startswith("#")
    ]


def test_engine_collect_keeps_effort_invocation_disabled_until_explicit_enablement():
    collect_source = inspect.getsource(EvidenceEngine.collect)
    hook_source = inspect.getsource(EvidenceEngine._collect_effort)

    assert "self._collect_effort()" in collect_source
    assert _active_collect_effort_calls(collect_source) == []
    assert "collect_effort(self._ctx)" in hook_source


def test_effort_greater_than_result_preflight_emits_zero_weight_neutral_context():
    evidence = collect_effort(
        _ctx(
            volume=VolumeClass.VERY_HIGH,
            spread=SpreadClass.NARROW,
            close=ClosePosition.LOWER,
        )
    )

    assert len(evidence) == 1

    item = evidence[0]
    assert item.code == EvidenceCode.EFFORT_GT_RESULT
    assert item.category == EvidenceCategory.EFFORT
    assert item.direction == EvidenceDirection.NEUTRAL
    assert item.weight == 0.0
    assert item.bar_index == 7
    assert item.week_beginning == "2026-03-02"


def test_result_greater_than_effort_preflight_emits_zero_weight_neutral_context():
    evidence = collect_effort(
        _ctx(
            volume=VolumeClass.LOW,
            spread=SpreadClass.WIDE,
            close=ClosePosition.UPPER,
            bar_index=8,
            week_beginning="2026-03-09",
        )
    )

    assert len(evidence) == 1

    item = evidence[0]
    assert item.code == EvidenceCode.RESULT_GT_EFFORT
    assert item.category == EvidenceCategory.EFFORT
    assert item.direction == EvidenceDirection.NEUTRAL
    assert item.weight == 0.0
    assert item.bar_index == 8
    assert item.week_beginning == "2026-03-09"


def test_weight_calculator_preflight_keeps_effort_family_non_scoring():
    ctx = _ctx()

    assert WeightCalculator.calculate(EvidenceCode.EFFORT_RESULT, ctx) == 0.0
    assert WeightCalculator.calculate(EvidenceCode.EFFORT_GT_RESULT, ctx) == 0.0
    assert WeightCalculator.calculate(EvidenceCode.RESULT_GT_EFFORT, ctx) == 0.0
    assert WeightCalculator.calculate(EvidenceCode.ABSORPTION, ctx) == 0.0


def test_preflight_does_not_backfill_absorption_or_emit_for_unrelated_profiles():
    high_effort_low_result = collect_effort(
        _ctx(
            volume=VolumeClass.VERY_HIGH,
            spread=SpreadClass.NARROW,
            close=ClosePosition.LOWER,
        )
    )
    unrelated = collect_effort(
        _ctx(
            volume=VolumeClass.AVERAGE,
            spread=SpreadClass.AVERAGE,
            close=ClosePosition.MIDDLE,
        )
    )

    assert EvidenceCode.EFFORT_GT_RESULT in {
        item.code for item in high_effort_low_result
    }
    assert EvidenceCode.ABSORPTION not in {
        item.code for item in high_effort_low_result
    }
    assert unrelated == []
