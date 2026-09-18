from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ScannerRecoveryPhase(StrEnum):
    """Production recovery/operational boundary where state handling changed."""

    LOAD_VALIDATE = "LOAD_VALIDATE"
    RESUME = "RESUME"
    PERSIST = "PERSIST"


@dataclass(frozen=True, slots=True)
class ScannerRecoveryEvent:
    """Structured production-scanner recovery telemetry.

    This is intentionally deterministic and transport-neutral. It carries the
    same fallback code/reason currently exposed through string diagnostics while
    also identifying the recovery phase and originating exception type.
    """

    code: str
    phase: ScannerRecoveryPhase
    reason: str
    symbol: str
    timeframe: str
    fallback_used: bool = True
    exception_type: str | None = None

    @property
    def message(self) -> str:
        suffix = (
            "full replay fallback used"
            if self.fallback_used
            else "full replay fallback not used"
        )
        return (
            f"{self.code}: {self.reason}; symbol={self.symbol}; "
            f"timeframe={self.timeframe}; {suffix}"
        )


__all__ = [
    "ScannerRecoveryEvent",
    "ScannerRecoveryPhase",
]
