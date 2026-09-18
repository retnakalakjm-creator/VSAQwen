from __future__ import annotations


class ScannerDomainError(ValueError):
    """Base ValueError for scanner-domain failures with actionable semantics."""


class ScannerTransitionError(ScannerDomainError):
    """Invalid causal transition request or transition state."""


class ScannerTransitionSequenceError(ScannerTransitionError):
    """Transition bars were not advanced sequentially."""


class ScannerTransitionStateMismatchError(ScannerTransitionError):
    """Transient transition state does not match the requested metrics history."""


class ScannerResumeError(ScannerDomainError):
    """Durable scanner state cannot be resumed against the supplied metrics."""


class ScannerResumeMetricsError(ScannerResumeError):
    """Current metrics cannot provide an unambiguous resume identity."""


class ScannerResumeCheckpointMissingError(ScannerResumeError):
    """The saved checkpoint bar is absent from current metrics."""


class ScannerResumeCheckpointBeyondMetricsError(ScannerResumeError):
    """The saved checkpoint is later than the available current metrics."""


class ScannerStateError(ScannerDomainError):
    """Persisted scanner-state validation or storage failure."""


class ScannerStateCorruptError(ScannerStateError):
    """Persisted scanner state cannot be decoded into a valid state object."""


class ScannerStateSchemaError(ScannerStateError):
    """Persisted scanner-state schema version is unsupported."""


class ScannerStateIdentityError(ScannerStateError):
    """Persisted scanner-state symbol/timeframe identity does not match."""


class ScannerStateWriteError(OSError):
    """Persisted scanner state could not be written atomically."""


__all__ = [
    "ScannerDomainError",
    "ScannerResumeCheckpointBeyondMetricsError",
    "ScannerResumeCheckpointMissingError",
    "ScannerResumeError",
    "ScannerResumeMetricsError",
    "ScannerStateCorruptError",
    "ScannerStateError",
    "ScannerStateIdentityError",
    "ScannerStateSchemaError",
    "ScannerStateWriteError",
    "ScannerTransitionError",
    "ScannerTransitionSequenceError",
    "ScannerTransitionStateMismatchError",
]
