from evidence.spring import _adjust_spring_quality_for_conflict
from models import EvidenceCode


def test_spring_quality_reduced_by_same_bar_upthrust():
    assert _adjust_spring_quality_for_conflict(1.0, {EvidenceCode.UPTHRUST}) == 0.5


def test_spring_quality_reduced_by_same_bar_buying_climax():
    assert _adjust_spring_quality_for_conflict(1.0, {EvidenceCode.BUYING_CLIMAX}) == 0.5


def test_spring_quality_unchanged_without_same_bar_conflict():
    assert _adjust_spring_quality_for_conflict(1.0, set()) == 1.0


def test_spring_quality_never_increases():
    assert _adjust_spring_quality_for_conflict(0.4, {EvidenceCode.UPTHRUST}) == 0.4
