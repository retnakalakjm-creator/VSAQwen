from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd
import pytest

import audit.daily_behavior_collision_universe as module
from audit.daily_behavior_collision_universe import (
    DailyBehaviorCollisionSymbolSummary,
    _normalize_symbols,
    _prepare_symbol,
    run_daily_behavior_collision_universe,
)
from audit.daily_behavior_sequence_runner import (
    DailyBehaviorSequenceDirectionAssignment,
    DailyBehaviorSequenceStudyInput,
)
from models import Evidence, EvidenceCategory, EvidenceCode, EvidenceDirection
from weekly_setup import WeeklySetupDirection


def _bars(rows: int = 6) -> pd.DataFrame:
    index = pd.bdate_range("2026-01-05", periods=rows, name="session")
    values = [100.0 + item for item in range(rows)]
    return pd.DataFrame(
        {
            "open": [value - 0.2 for value in values],
            "high": [value + 1.0 for value in values],
            "low": [value - 1.0 for value in values],
            "close": values,
            "volume": [1_000_000.0 + item * 10_000 for item in range(rows)],
        },
        index=index,
    )


def _evidence(
    code: EvidenceCode,
    direction: EvidenceDirection,
    bar_index: int,
) -> Evidence:
    return Evidence(
        code=code,
        category=EvidenceCategory.SIGNAL,
        direction=direction,
        strength=0.8,
        weight=1.0,
        observation=str(code),
        description=str(code),
        bar_index=bar_index,
        week_beginning=f"bar-{bar_index}",
    )


def test_normalize_symbols_rejects_symbol_absent_from_snapshot() -> None:
    with pytest.raises(ValueError, match="absent from snapshot"):
        _normalize_symbols(("LT.NS", "SRF.NS"), ("MISSING.NS",))


def test_prepare_symbol_uses_cached_k5_and_causal_k6(monkeypatch) -> None:
    daily = _bars()
    calls = {"cached": 0, "weekly": 0}

    monkeypatch.setattr(
        module,
        "load_daily_audit_input",
        lambda _root, _symbol: daily,
    )
    monkeypatch.setattr(
        module,
        "derive_historical_production_weekly_setups",
        lambda **_kwargs: SimpleNamespace(
            candidate_count=2,
            setup_count=1,
            setups=("setup",),
        ),
    )

    def fake_cached(**_kwargs):
        calls["cached"] += 1
        return SimpleNamespace(
            completed_daily=daily,
            evidence=(
                _evidence(
                    EvidenceCode.UPTHRUST,
                    EvidenceDirection.BEARISH,
                    2,
                ),
            ),
        )

    def fake_weekly(**_kwargs):
        calls["weekly"] += 1
        return SimpleNamespace(
            completed_daily=daily,
            assignments=(
                DailyBehaviorSequenceDirectionAssignment(
                    bar_index=2,
                    direction=WeeklySetupDirection.BEARISH,
                ),
            ),
        )

    monkeypatch.setattr(module, "produce_offline_daily_evidence_cached", fake_cached)
    monkeypatch.setattr(
        module,
        "produce_causal_weekly_direction_assignments",
        fake_weekly,
    )

    study_input, summary = _prepare_symbol(
        "snapshot",
        "LT.NS",
        "2026-01-12T00:00:00",
        0,
    )

    assert calls == {"cached": 1, "weekly": 1}
    assert study_input.symbol == "LT.NS"
    assert len(study_input.weekly_directions) == 1
    assert len(study_input.evidence) == 1
    assert summary.weekly_candidate_count == 2
    assert summary.weekly_setup_count == 1
    assert summary.bearish_assignment_count == 1
    assert summary.bullish_assignment_count == 0
    assert summary.k3_input_fingerprint.startswith("sha256:")


def test_universe_run_reports_coarse_collision_without_actionability(
    monkeypatch,
    tmp_path,
) -> None:
    bars = _bars().loc[:, ["close", "high", "low"]]
    study_input = DailyBehaviorSequenceStudyInput(
        symbol="LT.NS",
        bars=bars,
        weekly_directions=(
            DailyBehaviorSequenceDirectionAssignment(
                bar_index=2,
                direction=WeeklySetupDirection.BEARISH,
            ),
            DailyBehaviorSequenceDirectionAssignment(
                bar_index=4,
                direction=WeeklySetupDirection.BEARISH,
            ),
        ),
        evidence=(
            _evidence(
                EvidenceCode.BUYING_CLIMAX,
                EvidenceDirection.BEARISH,
                2,
            ),
            _evidence(
                EvidenceCode.UPTHRUST,
                EvidenceDirection.BEARISH,
                4,
            ),
        ),
    )
    symbol_summary = DailyBehaviorCollisionSymbolSummary(
        symbol="LT.NS",
        daily_bar_count=len(bars),
        daily_evidence_count=2,
        weekly_candidate_count=2,
        weekly_setup_count=1,
        weekly_direction_assignment_count=2,
        bullish_assignment_count=0,
        bearish_assignment_count=2,
        k3_input_fingerprint="sha256:test",
    )

    monkeypatch.setattr(
        module,
        "load_daily_audit_input_bundle",
        lambda _root: SimpleNamespace(
            basket_name="test-basket",
            cutoff="2026-01-12T00:00:00",
            fingerprints=(SimpleNamespace(symbol="LT.NS"),),
        ),
    )
    monkeypatch.setattr(
        module,
        "daily_audit_input_manifest_sha256",
        lambda _root: "manifest-sha",
    )
    monkeypatch.setattr(
        module,
        "_prepare_symbol",
        lambda *_args: (study_input, symbol_summary),
    )

    result = run_daily_behavior_collision_universe(
        input_snapshot_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        workers=1,
        min_target_index=0,
        horizons_bars=(1,),
        lookback_bars=1,
    )

    payload = json.loads(result.summary_json.read_text(encoding="utf-8"))
    collisions = pd.read_csv(
        result.study_paths.signature_collisions_csv
        if result.study_paths is not None
        else ""
    )

    assert result.failed_symbol_count == 0
    assert payload["coarse_signature_collision_count"] == 1
    assert payload["collision_observation_count"] == 2
    assert payload["is_actionable"] is False
    assert len(collisions) == 1
    assert collisions["is_actionable"].eq(False).all()
