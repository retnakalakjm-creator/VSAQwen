from pathlib import Path

import models


MATRIX_PATH = Path(__file__).parents[1] / "docs" / "PRIMARY_VSA_EVENT_MATRIX.md"


def test_primary_vsa_event_matrix_exists() -> None:
    assert MATRIX_PATH.is_file()
    text = MATRIX_PATH.read_text(encoding="utf-8")
    assert "# Primary VSA Event Matrix" in text


def test_core_production_vsa_events_are_documented() -> None:
    text = MATRIX_PATH.read_text(encoding="utf-8")

    for code in (
        "BUYING_CLIMAX",
        "SUPPLY_COMING_IN",
        "INCREASING_SUPPLY",
        "HIDDEN_SUPPLY",
        "SUPPLY_DRYING_UP",
        "UPTHRUST",
        "NO_DEMAND",
        "SHAKEOUT",
        "STRUCTURAL_PROGRESSION_IMPROVING",
        "STRUCTURAL_PROGRESSION_WEAKENING",
    ):
        assert f"`{code}`" in text


def test_known_bullish_gap_events_are_explicitly_called_out() -> None:
    text = MATRIX_PATH.read_text(encoding="utf-8")

    for code in (
        "STOPPING_VOLUME",
        "DEMAND_COMING_IN",
        "INCREASING_DEMAND",
        "HIDDEN_DEMAND",
        "DEMAND_DRYING_UP",
        "NO_SUPPLY",
        "SELLING_CLIMAX",
        "TEST",
        "SPRING",
    ):
        assert f"`{code}`" in text


def test_matrix_covers_every_evidence_code_enum_member() -> None:
    text = MATRIX_PATH.read_text(encoding="utf-8")

    missing = [
        member.name
        for member in models.EvidenceCode
        if f"`{member.name}`" not in text
    ]

    assert not missing, f"Undocumented EvidenceCode members: {missing}"
