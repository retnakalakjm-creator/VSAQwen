from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class StructureContext:
    """
    Overall structural assessment of the market
    around the current swing.
    """

    strength: float

    weakness: float

    buying_pressure: float

    selling_pressure: float

    confidence: float