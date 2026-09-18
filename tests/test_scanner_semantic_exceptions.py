from __future__ import annotations

import pytest

from scanner_exceptions import (
    ScannerDomainError,
    ScannerResumeCheckpointMissingError,
    ScannerResumeMetricsError,
    ScannerStateCorruptError,
    ScannerStateIdentityError,
    ScannerStateSchemaError,
    ScannerTransitionSequenceError,
    ScannerTransitionStateMismatchError,
)


@pytest.mark.parametrize(
    "error_type",
    (
        ScannerResumeCheckpointMissingError,
        ScannerResumeMetricsError,
        ScannerStateCorruptError,
        ScannerStateIdentityError,
        ScannerStateSchemaError,
        ScannerTransitionSequenceError,
        ScannerTransitionStateMismatchError,
    ),
)
def test_semantic_scanner_errors_preserve_value_error_compatibility(error_type) -> None:
    error = error_type("test")

    assert isinstance(error, ScannerDomainError)
    assert isinstance(error, ValueError)


def test_semantic_scanner_errors_remain_precisely_catchable() -> None:
    with pytest.raises(ScannerResumeCheckpointMissingError, match="checkpoint"):
        raise ScannerResumeCheckpointMissingError("checkpoint is missing")

    with pytest.raises(ScannerTransitionSequenceError, match="sequential"):
        raise ScannerTransitionSequenceError("steps must be sequential")
