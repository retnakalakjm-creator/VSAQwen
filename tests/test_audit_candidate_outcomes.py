from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pytest

from audit.candidates import (
    build_candidate_outcome_frame,
    build_candidate_outcome_rows,
    default_candidate_side,
)
from audit.outcomes import OutcomeSide
from background.qualification import PatternQualification


@dataclass(frozen=True)
class CandidateSnapshot:
    qualification: PatternQualification
    bar_index: int
    week: str
    actionable: bool = True
    confidence: float = 0.75
    net_strength: float = 1.2
    net_pressure: float = 0.8
    scoring_bar_index: int | None = 1
    scoring_evidence_age: int | None = 0
    used_fallback_evidence: bool = False
    signal_bar_anomaly: bool = False
    signal_bar_anomaly_reason: str | None = None
    reason: str = "test candidate"
    target_bar_evidence_codes: tuple[str, ...] = ("stopping_volume",)
    qualifying_evidence_codes: tuple[str, ...] = ("structural_progression_improving",)
    scoring_evidence_codes: tuple[str, ...] = ("stopping_volume",)
    campaign_evidence_codes: tuple[str, ...] = ("stopping_volume", "structural_progression_improving")

    @property
    def signal_bar_index(self) -> int:
        return self.bar_index

    @property
    def signal_week(self) -> str:
        return self.week

    @property
    def execution_bar_index(self) -> int | None:
        next_index = self.bar_index + 1
        return next_index if next_index < 5 else None

    @property
    def execution_week(self) -> str | None:
        return f"week-{self.execution_bar_index}" if self.execution_bar_index is not None else None


def _bars() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "close": [100.0, 105.0, 110.0, 108.0, 120.0],
            "high": [101.0, 106.0, 112.0, 111.0, 122.0],
            "low": [99.0, 104.0, 109.0, 107.0, 119.0],
        }
    )


def test_default_candidate_side_uses_persistent_qualification() -> None:
    assert default_candidate_side({"qualification": PatternQualification.PERSISTENT_BULLISH}) is OutcomeSide.LONG
    assert default_candidate_side({"qualification": PatternQualification.PERSISTENT_BEARISH}) is OutcomeSide.SHORT
    assert default_candidate_side({"qualification": PatternQualification.UNQUALIFIED}) is OutcomeSide.NEUTRAL


def test_candidate_outcome_rows_attach_next_bar_execution_outcomes() -> None:
    candidate = CandidateSnapshot(
        qualification=PatternQualification.PERSISTENT_BULLISH,
        bar_index=1,
        week="2026-01-05",
    )

    rows = build_candidate_outcome_rows(
        _bars(),
        [candidate],
        horizons=[1, 2],
        symbol="SRF.NS",
    )

    assert len(rows) == 2
    assert rows[0].symbol == "SRF.NS"
    assert rows[0].candidate_id == 0
    assert rows[0].signal_bar_index == 1
    assert rows[0].execution_bar_index == 2
    assert rows[0].outcome_execution_bar_index == 2
    assert rows[0].exit_bar_index == 3
    assert rows[0].side == "long"
    assert rows[0].qualification == "persistent_bullish"
    assert rows[0].target_bar_evidence_codes == "stopping_volume"
    assert rows[0].campaign_evidence_codes == "stopping_volume|structural_progression_improving"
    assert rows[0].outcome_available is True
    assert rows[0].complete is True
    assert rows[0].raw_return == pytest.approx(-2 / 110)
    assert rows[1].exit_bar_index == 4
    assert rows[1].raw_return == pytest.approx(10 / 110)


def test_candidate_outcome_frame_is_flat_and_deterministic() -> None:
    candidates = [
        CandidateSnapshot(
            qualification=PatternQualification.PERSISTENT_BULLISH,
            bar_index=1,
            week="2026-01-05",
        ),
        CandidateSnapshot(
            qualification=PatternQualification.PERSISTENT_BEARISH,
            bar_index=2,
            week="2026-01-12",
            net_pressure=-0.9,
            target_bar_evidence_codes=("upthrust",),
            qualifying_evidence_codes=("structural_progression_weakening",),
            scoring_evidence_codes=("upthrust",),
            campaign_evidence_codes=("upthrust", "structural_progression_weakening"),
        ),
    ]

    frame = build_candidate_outcome_frame(
        _bars(),
        candidates,
        horizons=[1],
        symbol="TEST.NS",
    )

    assert list(frame["candidate_id"]) == [0, 1]
    assert list(frame["side"]) == ["long", "short"]
    assert list(frame["signal_bar_index"]) == [1, 2]
    assert list(frame["horizon_bars"]) == [1, 1]
    assert frame.loc[1, "target_bar_evidence_codes"] == "upthrust"
    assert frame.loc[1, "favorable_return"] == pytest.approx(-12 / 108)


def test_latest_candidate_without_execution_bar_can_be_retained_as_unscored() -> None:
    latest = CandidateSnapshot(
        qualification=PatternQualification.PERSISTENT_BULLISH,
        bar_index=4,
        week="2026-02-02",
    )

    rows = build_candidate_outcome_rows(
        _bars(),
        [latest],
        horizons=[1, 3],
        symbol="LATEST.NS",
        include_unscored=True,
    )

    assert len(rows) == 2
    assert all(row.outcome_available is False for row in rows)
    assert all(row.entry_price is None for row in rows)
    assert all(row.complete is False for row in rows)
    assert {row.horizon_bars for row in rows} == {1, 3}


def test_latest_candidate_without_execution_bar_can_be_omitted() -> None:
    latest = CandidateSnapshot(
        qualification=PatternQualification.PERSISTENT_BULLISH,
        bar_index=4,
        week="2026-02-02",
    )

    rows = build_candidate_outcome_rows(
        _bars(),
        [latest],
        horizons=[1],
        include_unscored=False,
    )

    assert rows == []


def test_mapping_candidates_are_supported_for_serialized_snapshots() -> None:
    rows = build_candidate_outcome_rows(
        _bars(),
        [
            {
                "symbol": "DICT.NS",
                "qualification": "persistent_bearish",
                "signal_bar_index": 2,
                "signal_week": "2026-01-12",
                "actionable": True,
                "confidence": 0.5,
                "net_strength": -1.0,
                "net_pressure": -0.4,
                "target_bar_evidence_codes": ["upthrust"],
            }
        ],
        horizons=[1],
        symbol="IGNORED.NS",
    )

    assert len(rows) == 1
    assert rows[0].symbol == "DICT.NS"
    assert rows[0].side == "short"
    assert rows[0].target_bar_evidence_codes == "upthrust"


def test_custom_side_resolver_can_override_qualification_direction() -> None:
    candidate = CandidateSnapshot(
        qualification=PatternQualification.UNQUALIFIED,
        bar_index=1,
        week="2026-01-05",
    )

    rows = build_candidate_outcome_rows(
        _bars(),
        [candidate],
        horizons=[1],
        side_resolver=lambda _candidate: OutcomeSide.LONG,
    )

    assert rows[0].side == "long"
    assert rows[0].favorable_return == rows[0].raw_return


def test_empty_or_invalid_horizons_are_rejected() -> None:
    candidate = CandidateSnapshot(
        qualification=PatternQualification.PERSISTENT_BULLISH,
        bar_index=1,
        week="2026-01-05",
    )

    with pytest.raises(ValueError, match="horizons"):
        build_candidate_outcome_rows(_bars(), [candidate], horizons=[])

    with pytest.raises(ValueError, match="greater than zero"):
        build_candidate_outcome_rows(_bars(), [candidate], horizons=[0])
