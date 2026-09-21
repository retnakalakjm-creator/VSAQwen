from __future__ import annotations

from audit.daily_event_bc_upthrust_identity_separation import (
    BC_CODE,
    BC_UNIQUE_CONFIRMATION,
    PARTITION_BC_ONLY,
    PARTITION_BOTH,
    PARTITION_NEITHER,
    PARTITION_UT_ONLY,
    SHARED_CONFIRMATIONS,
    SHARED_MANDATORY_REQUIREMENTS,
    UT_CODE,
    UT_UNIQUE_CONFIRMATION,
    partition_unique_confirmations,
)
from audit.daily_event_confirmation_semantics import (
    build_confirmation_contract_rows,
)


def _names(code: str, kind: str) -> tuple[str, ...]:
    return tuple(
        row.requirement_name
        for row in build_confirmation_contract_rows()
        if row.code == code and row.requirement_kind == kind
    )


def test_historical_collision_contract_is_no_longer_live_production() -> None:
    bc = _names(BC_CODE, "MANDATORY")
    ut = _names(UT_CODE, "MANDATORY")

    assert SHARED_MANDATORY_REQUIREMENTS == (
        "Buying Campaign",
        "Bullish Bar",
        "Very High Volume",
        "Above Average Spread",
    )
    assert bc != SHARED_MANDATORY_REQUIREMENTS
    assert ut != SHARED_MANDATORY_REQUIREMENTS
    assert bc != ut

    assert bc[-1] == "Non-Strong High Acceptance"
    assert ut == (
        "Confirmed Structural High",
        "Probe Above Structural High",
        "Failed Acceptance Above Structural High",
    )


def test_historical_unique_confirmation_hypothesis_remains_frozen() -> None:
    assert SHARED_CONFIRMATIONS == ("Wide Spread", "Weak Close")
    assert BC_UNIQUE_CONFIRMATION == "Increasing Volume"
    assert UT_UNIQUE_CONFIRMATION == "Lower Close Than Previous"

    assert _names(BC_CODE, "CONFIRMATION") == (
        "Wide Spread",
        "Weak Close",
        "Increasing Volume",
    )
    assert _names(UT_CODE, "CONFIRMATION") == (
        "Weak Close",
        "Very High Volume",
        "Above Average Spread",
    )


def test_unique_confirmation_partition_truth_table() -> None:
    assert (
        partition_unique_confirmations(
            bc_passed=True,
            ut_passed=False,
        )
        == PARTITION_BC_ONLY
    )
    assert (
        partition_unique_confirmations(
            bc_passed=False,
            ut_passed=True,
        )
        == PARTITION_UT_ONLY
    )
    assert (
        partition_unique_confirmations(
            bc_passed=True,
            ut_passed=True,
        )
        == PARTITION_BOTH
    )
    assert (
        partition_unique_confirmations(
            bc_passed=False,
            ut_passed=False,
        )
        == PARTITION_NEITHER
    )
