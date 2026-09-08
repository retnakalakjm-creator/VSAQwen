from __future__ import annotations

import config
from market_structure.structure_filter import StructureFilter
from models import SwingGrade


def test_grade_swing_maps_score_bands(monkeypatch) -> None:
    monkeypatch.setattr(config, "STRUCTURE_INTERMEDIATE_GRADE_SCORE", 0.65, raising=False)
    monkeypatch.setattr(config, "STRUCTURE_MAJOR_GRADE_SCORE", 0.80, raising=False)

    structure_filter = StructureFilter()

    assert structure_filter._grade_swing(0.50) is SwingGrade.MINOR
    assert structure_filter._grade_swing(0.6499) is SwingGrade.MINOR
    assert structure_filter._grade_swing(0.65) is SwingGrade.INTERMEDIATE
    assert structure_filter._grade_swing(0.7999) is SwingGrade.INTERMEDIATE
    assert structure_filter._grade_swing(0.80) is SwingGrade.MAJOR
    assert structure_filter._grade_swing(1.00) is SwingGrade.MAJOR


def test_is_structural_still_uses_minimum_structure_score(monkeypatch) -> None:
    monkeypatch.setattr(config, "MIN_STRUCTURE_SCORE", 0.50)

    structure_filter = StructureFilter()

    assert not structure_filter._is_structural(0.4999)
    assert structure_filter._is_structural(0.50)
