"""Market universe definitions used by the ProVSA GUI."""

from __future__ import annotations

from dataclasses import dataclass


# Temporary experimental subset. Restore the full NIFTY 50 after GUI testing.
BUILTIN_UNIVERSES: dict[str, tuple[str, ...]] = {
    "NIFTY 50": (
        "RELIANCE.NS",
        "HDFCBANK.NS",
        "ICICIBANK.NS",
        "INFY.NS",
        "TCS.NS",
    ),
}


@dataclass(frozen=True, slots=True)
class MarketUniverse:
    symbols: tuple[str, ...]

    def __post_init__(self) -> None:
        normalized = tuple(
            dict.fromkeys(
                symbol.strip().upper()
                for symbol in self.symbols
                if symbol.strip()
            )
        )
        object.__setattr__(self, "symbols", normalized)

    @classmethod
    def from_text(cls, text: str) -> "MarketUniverse":
        return cls(tuple(line for line in text.splitlines()))
