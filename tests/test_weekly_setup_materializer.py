from __future__ import annotations

from types import SimpleNamespace

import pytest

from background.qualification import PatternQualification
from weekly_setup import WeeklySetupDirection, WeeklySetupStatus
from weekly_setup_materializer import materialize_production_weekly_setup


def _candidate(**overrides):
    values = {
        "actionable": True,
        "qualification": PatternQualification.PERSISTENT_BULLISH,
        "week": "2026-09-14 00:00:00",
        "confidence": 0.82,
        "net_strength": 1.25,
        "net_pressure": 0.74,
        "qualifying_evidence": ("structural-1", "structural-2", "structural-3"),
        "scoring_evidence": ("production-vsa",),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_materializer_builds_armed_setup_from_authoritative_bullish_candidate() -> None:
    setup = materialize_production_weekly_setup(
        _candidate(),
        symbol=" lt.ns ",
    )

    assert setup is not None
    assert setup.setup_id == "LT.NS:2026-09-14 00:00:00:bullish"
    assert setup.symbol == "LT.NS"
    assert setup.direction is WeeklySetupDirection.BULLISH
    assert setup.qualification is PatternQualification.PERSISTENT_BULLISH
    assert setup.status is WeeklySetupStatus.ARMED
    assert setup.weekly_confidence == 0.82
    assert setup.weekly_net_strength == 1.25
    assert setup.weekly_net_pressure == 0.74
    assert setup.qualifying_evidence == (
        "structural-1",
        "structural-2",
        "structural-3",
    )
    assert setup.supporting_evidence == ("production-vsa",)
    assert setup.support_zone is None
    assert setup.resistance_zone is None
    assert setup.invalidation_level is None


def test_materializer_maps_persistent_bearish_candidate_symmetrically() -> None:
    setup = materialize_production_weekly_setup(
        _candidate(
            qualification=PatternQualification.PERSISTENT_BEARISH,
            net_strength=-1.1,
            net_pressure=-0.9,
        ),
        symbol="ABC.NS",
    )

    assert setup is not None
    assert setup.direction is WeeklySetupDirection.BEARISH
    assert setup.qualification is PatternQualification.PERSISTENT_BEARISH
    assert setup.setup_id.endswith(":bearish")


@pytest.mark.parametrize(
    "candidate",
    (
        _candidate(actionable=False),
        _candidate(
            actionable=True,
            qualification=PatternQualification.UNQUALIFIED,
        ),
    ),
)
def test_materializer_does_not_create_setup_without_existing_production_authority(
    candidate,
) -> None:
    assert (
        materialize_production_weekly_setup(candidate, symbol="LT.NS")
        is None
    )


def test_materializer_uses_scoring_evidence_not_broader_observation_layers() -> None:
    candidate = _candidate(
        scoring_evidence=("production-scoring-evidence",),
        target_bar_evidence=("read-only-observation",),
        campaign_evidence=("campaign-observation",),
    )

    setup = materialize_production_weekly_setup(candidate, symbol="LT.NS")

    assert setup is not None
    assert setup.supporting_evidence == ("production-scoring-evidence",)


def test_actionable_candidate_requires_signal_week() -> None:
    with pytest.raises(ValueError, match="signal week"):
        materialize_production_weekly_setup(
            _candidate(week=None),
            symbol="LT.NS",
        )


def test_materializer_rejects_blank_symbol() -> None:
    with pytest.raises(ValueError, match="symbol must not be empty"):
        materialize_production_weekly_setup(_candidate(), symbol="   ")
