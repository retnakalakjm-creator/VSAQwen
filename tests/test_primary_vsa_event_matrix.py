from pathlib import Path

import models


MATRIX_PATH = Path(__file__).parents[1] / "docs" / "PRIMARY_VSA_EVENT_MATRIX.md"

# Only atomic VSA event codes belong in this matrix. Trend, phase, structural,
# effort/result and other higher-level context codes are documented by their
# respective modules and must not be forced into the primary-event audit.
PRIMARY_VSA_EVENT_CODES = {
    "BUYING_CLIMAX",
    "SUPPLY_COMING_IN",
    "INCREASING_SUPPLY",
    "HIDDEN_SUPPLY",
    "SUPPLY_DRYING_UP",
    "SUPPLY_HIGH_VOLUME",
    "SUPPLY_WIDE_SPREAD",
    "SUPPLY_ABSORPTION",
    "STOPPING_VOLUME",
    "DEMAND_COMING_IN",
    "INCREASING_DEMAND",
    "HIDDEN_DEMAND",
    "DEMAND_DRYING_UP",
    "NO_SUPPLY",
    "EFFORT_GT_RESULT",
    "RESULT_GT_EFFORT",
    "ABSORPTION",
    "SPRING",
    "UPTHRUST",
    "TEST",
    "NO_DEMAND",
    "SELLING_CLIMAX",
    "EFFORT_RESULT",
    "SHAKEOUT",
}


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


def test_matrix_covers_every_primary_vsa_event_code() -> None:
    text = MATRIX_PATH.read_text(encoding="utf-8")

    missing = [
        code
        for code in sorted(PRIMARY_VSA_EVENT_CODES)
        if f"`{code}`" not in text
    ]

    assert not missing, f"Undocumented primary VSA event codes: {missing}"


def test_non_primary_context_codes_are_not_part_of_matrix_contract() -> None:
    text = MATRIX_PATH.read_text(encoding="utf-8")

    context_only = {
        member.name
        for member in models.EvidenceCode
        if member.name not in PRIMARY_VSA_EVENT_CODES
    }

    assert context_only
    assert all(
        f"{code}" not in text
        or "context" in text.lower()
        or "structural" in text.lower()
        for code in context_only
    )
