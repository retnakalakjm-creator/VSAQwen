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


def test_bc_and_upthrust_share_exact_mandatory_contract() -> None:
    bc = _names(BC_CODE, "MANDATORY")
    ut = _names(UT_CODE, "MANDATORY")

    assert bc == SHARED_MANDATORY_REQUIREMENTS
    assert ut == SHARED_MANDATORY_REQUIREMENTS
    assert bc == ut


def test_bc_and_upthrust_have_two_shared_and_one_unique_confirmation() -> None:
    bc = _names(BC_CODE, "CONFIRMATION")
    ut = _names(UT_CODE, "CONFIRMATION")

    assert bc == (*SHARED_CONFIRMATIONS, BC_UNIQUE_CONFIRMATION)
    assert ut == (*SHARED_CONFIRMATIONS, UT_UNIQUE_CONFIRMATION)


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
