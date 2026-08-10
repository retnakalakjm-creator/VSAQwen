from __future__ import annotations

from typing import Protocol

from models import (
    SmartMoneyEvidence,
    SwingContext,
)


class EvidenceRule(Protocol):
    """
    Contract implemented by every Smart Money
    evidence detector.
    """

    def __call__(
        self,
        ctx: SwingContext,
    ) -> SmartMoneyEvidence | None:
        ...