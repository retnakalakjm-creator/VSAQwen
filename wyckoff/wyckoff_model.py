"""
Professional Wyckoff Result Models.
"""

from dataclasses import dataclass
from enum import IntEnum, StrEnum, auto

from models import Evidence


class WyckoffPhase(IntEnum):
    UNKNOWN = auto()

    ACCUMULATION = auto()
    REACCUMULATION = auto()

    MARKUP = auto()

    DISTRIBUTION = auto()
    REDISTRIBUTION = auto()

    MARKDOWN = auto()


class WyckoffEvent(IntEnum):
    NONE = auto()

    SPRING = auto()
    TERMINAL_SHAKEOUT = auto()

    TEST = auto()

    SIGN_OF_STRENGTH = auto()
    LAST_POINT_OF_SUPPORT = auto()

    BUYING_CLIMAX = auto()

    UPTHRUST = auto()
    UPTHRUST_AFTER_DISTRIBUTION = auto()

    NO_DEMAND = auto()
    NO_SUPPLY = auto()

    SIGN_OF_WEAKNESS = auto()
    LAST_POINT_OF_SUPPLY = auto()

    STOPPING_VOLUME = auto()

    SHAKEOUT = auto()


class MarketBias(StrEnum):
    """
    Overall professional market bias.
    """

    UNKNOWN = auto()

    BULLISH = auto()

    BEARISH = auto()

    NEUTRAL = auto()


@dataclass(
    slots=True,
    frozen=True,
)
class WyckoffResult:

    phase: WyckoffPhase

    events: tuple[WyckoffEvent, ...]

    bias: MarketBias

    confidence: float

    summary: str
    
    @property
    def has_events(self) -> bool:
        return bool(self.events)

    @property
    def is_accumulation(self) -> bool:
        return self.phase == WyckoffPhase.ACCUMULATION
    
    @property
    def is_reaccumulation(self) -> bool:
        return self.phase == WyckoffPhase.REACCUMULATION

    @property
    def is_distribution(self) -> bool:
        return self.phase == WyckoffPhase.DISTRIBUTION
    
    @property
    def is_redistribution(self) -> bool:
        return self.phase == WyckoffPhase.REDISTRIBUTION

    @property
    def is_markup(self) -> bool:
        return self.phase == WyckoffPhase.MARKUP    

    @property
    def is_markdown(self) -> bool:
        return self.phase == WyckoffPhase.MARKDOWN
    
    @property
    def is_unknown(self) -> bool:
        return self.phase == WyckoffPhase.UNKNOWN
    
    @property
    def event_count(self) -> int:
        return len(self.events)
    
   