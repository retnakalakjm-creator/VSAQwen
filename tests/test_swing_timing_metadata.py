from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from api.service import ProVSAService
from models import SwingType


def _structural_swing_fixture(*, bar_index: int = 1, confirmation_index: int = 3):
    swing = SimpleNamespace(
        bar_index=bar_index,
        confirmation_index=confirmation_index,
        week_beginning="2026-01-12",
        type=SwingType.LOW,
        price=98.5,
    )
    structure_score = SimpleNamespace(
        price=1.0,
        structural_size=0.8,
        duration=0.7,
        volume=0.6,
        spread=0.5,
        overall=0.75,
    )
    smart_money_score = SimpleNamespace(overall=0.66)
    professional_score = SimpleNamespace(
        structure=structure_score,
        smart_money=smart_money_score,
        overall=0.7,
    )
    evaluation = SimpleNamespace(professional=professional_score)
    grade = SimpleNamespace(name="MAJOR")
    return SimpleNamespace(
        swing=swing,
        evaluation=evaluation,
        grade=grade,
        is_failed=False,
    )


def _weekly_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "week_beginning": [
                "2026-01-05",
                "2026-01-12",
                "2026-01-19",
                "2026-01-26",
            ]
        }
    )


def test_structural_swing_dto_exposes_pivot_and_confirmation_metadata() -> None:
    item = _structural_swing_fixture()
    labels = {(SwingType.LOW, 1): "HL"}

    dto = ProVSAService._structural_swing(item, labels, _weekly_frame())

    assert dto.bar_index == 1
    assert dto.week == "2026-01-12"
    assert dto.confirmation_index == 3

    assert dto.pivot_bar_index == 1
    assert dto.pivot_week == "2026-01-12"
    assert dto.confirmation_bar_index == 3
    assert dto.confirmation_week == "2026-01-26"
    assert dto.label == "HL"


def test_structural_swing_rejects_missing_confirmation_week() -> None:
    item = _structural_swing_fixture(confirmation_index=99)

    with pytest.raises(IndexError, match="swing index is outside weekly bars"):
        ProVSAService._structural_swing(item, {}, _weekly_frame())
