from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class SwingObservation:
    """
    One piece of VSA background evidence.
    """

    name: str

    bullish: bool

    weight: float

    description: str = ""