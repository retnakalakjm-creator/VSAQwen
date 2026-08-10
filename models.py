"""
Professional VSA Swing Scanner
Core Models
"""

from __future__ import annotations
from typing import TYPE_CHECKING

from dataclasses import dataclass, field,replace
from enum import Enum, IntEnum, StrEnum, auto
from functools import cached_property

import pandas as pd

from utils.scoring import ScoreComponent, combine_scores, component
if TYPE_CHECKING:
    from model.evidence_result_model import EvidenceResult

if TYPE_CHECKING:
    from market_structure.swing_history import SwingHistoryAnalyzer



# =============================================================================
# BASIC BAR CLASSIFICATION
# =============================================================================

class Direction(IntEnum):
    DOWN = -1
    NEUTRAL = 0
    UP = 1


class VolumeClass(IntEnum):
    """
    Professional VSA volume classification.
    """    
    ULTRA_LOW = auto()
    VERY_LOW = auto()
    LOW = auto()
    AVERAGE = auto()    
    HIGH = auto()
    VERY_HIGH = auto()
    ULTRA_HIGH = auto()


class SpreadClass(IntEnum):
    """
    Professional VSA spread classification.
    """
    NARROW = auto()
    BELOW_AVERAGE = auto()
    AVERAGE = auto()
    ABOVE_AVERAGE = auto()
    WIDE = auto()
    VERY_WIDE = auto()


class ClosePosition(IntEnum):
    ON_LOW = 0
    LOWER = 1
    MIDDLE = 2
    UPPER = 3
    ON_HIGH = 4


# =============================================================================
# Evidence Categories
# =============================================================================

class EvidenceCategory(IntEnum):
    SUPPLY = auto()
    DEMAND = auto()
    EFFORT = auto()    
    TREND = auto()
    PHASE = auto()
    VOLUME = auto()
    SPREAD = auto()
    SIGNAL = auto()
    RESULT = auto()
    ABSORPTION = auto()
    EXHAUSTION = auto()
    CONTINUATION = auto()
    TRAP = auto()


# =============================================================================
# Evidence Strength
# =============================================================================
class EvidenceStrength(Enum):

    WEAK = auto()

    MODERATE = auto()

    STRONG = auto()

    MAJOR = auto()



# =============================================================================
# Evidence Code
# =============================================================================    

class EvidenceCode(StrEnum):
    
    """
    Atomic market observations produced by the
    Evidence Engine.
    """

    # ==========================================================
    # Supply
    # ==========================================================

    BUYING_CLIMAX = auto()
    SUPPLY_COMING_IN = auto()
    INCREASING_SUPPLY = auto()
    HIDDEN_SUPPLY = auto()
    SUPPLY_DRYING_UP = auto()
    SUPPLY_HIGH_VOLUME = auto()
    SUPPLY_WIDE_SPREAD = auto()
    SUPPLY_ABSORPTION = auto()
    

    # ==========================================================
    # Demand
    # ==========================================================

    STOPPING_VOLUME = auto()
    DEMAND_COMING_IN = auto()
    INCREASING_DEMAND = auto()
    HIDDEN_DEMAND = auto()
    DEMAND_DRYING_UP = auto()
    NO_SUPPLY = auto()

    # ==========================================================
    # Effort vs Result
    # ==========================================================

    EFFORT_GT_RESULT = auto()
    RESULT_GT_EFFORT = auto()
    ABSORPTION = auto()

    # ==========================================================
    # Trend
    # ==========================================================

    STRONG_UPTREND = auto()
    WEAK_UPTREND = auto()

    STRONG_DOWNTREND = auto()
    WEAK_DOWNTREND = auto()

    SIDEWAYS_MARKET = auto()

    # ==========================================================
    # Wyckoff Phase
    # ==========================================================

    ACCUMULATION = auto()
    REACCUMULATION = auto()

    MARKUP = auto()

    DISTRIBUTION = auto()
    REDISTRIBUTION = auto()

    MARKDOWN = auto()

    SPRING = auto()
    UPTHRUST = auto()
    TEST = auto()
    NO_DEMAND = auto()    
    SELLING_CLIMAX = auto()
    EFFORT_RESULT = auto()
    
    SHAKEOUT = auto()

    STRUCTURAL_PROGRESSION_IMPROVING = auto()
    STRUCTURAL_PROGRESSION_WEAKENING = auto()
    

# =============================================================================
# Evidence Direction
# =============================================================================

class EvidenceDirection(IntEnum):

    BULLISH = 1

    NEUTRAL = 0

    BEARISH = -1   


# =============================================================================
# BACKGROUND
# =============================================================================

class BackgroundStrength(IntEnum):
    VERY_WEAK = 0
    WEAK = 1
    NEUTRAL = 2
    STRONG = 3
    VERY_STRONG = 4


class MarketPhase(IntEnum):
    UNKNOWN = 0
    ACCUMULATION = 1
    MARKUP = 2
    DISTRIBUTION = 3
    MARKDOWN = 4


# =============================================================================
# SIGNALS
# =============================================================================

class SignalType(IntEnum):
    NONE = 0

    # Strength
    STOPPING_VOLUME = auto()
    SELLING_CLIMAX = auto()
    TEST = auto()
    SUCCESSFUL_TEST = auto()
    NO_SUPPLY = auto()
    SHAKEOUT = auto()
    SIGN_OF_STRENGTH = auto()
    EFFORT_TO_RISE = auto()

    # Weakness
    BUYING_CLIMAX = auto()
    UPTHRUST = auto()
    NO_DEMAND = auto()
    SUPPLY_COMING_IN = auto()
    SIGN_OF_WEAKNESS = auto()
    EFFORT_TO_FALL = auto()


# =============================================================================
# SwingType
# =============================================================================

class SwingType(StrEnum):
    HIGH = auto()
    LOW = auto()


# =============================================================================
# SwingLabel
# =============================================================================

class SwingLabel(StrEnum):
    HH = auto()
    HL = auto()
    LH = auto()
    LL = auto()


class SwingGrade(Enum):
    """
    Structural importance of a confirmed swing.
    """

    MINOR = auto()

    INTERMEDIATE = auto()

    MAJOR = auto()



# =============================================================================
# SwingSearchState
# =============================================================================

class SwingSearchState(StrEnum):

    TRACKING_HIGH = auto()

    WAITING_HIGH_CONFIRMATION = auto()

    TRACKING_LOW = auto()

    WAITING_LOW_CONFIRMATION = auto()



# =============================================================================
# TrendDirection
# =============================================================================

class TrendDirection(StrEnum):
    UNKNOWN = auto()
    UP = auto()
    DOWN = auto()
    RANGE = auto()


# =============================================================================
# TrendState
# =============================================================================

class TrendState(StrEnum):
    UNKNOWN = auto()
    DEVELOPING = auto()
    HEALTHY = auto()
    CORRECTING = auto()
    EXHAUSTED = auto()
    REVERSING = auto()


# =============================================================================
# Market Bias
# =============================================================================

class MarketBias(StrEnum):
    """
    Overall Smart Money bias derived from the
    accumulated VSA evidence.
    """

    BULLISH = auto()

    BEARISH = auto()

    NEUTRAL = auto()


# =============================================================================
# Wyckoff Phase
# =============================================================================

class WyckoffPhase(StrEnum):
    """
    Wyckoff market phase inferred from
    trend and background evidence.
    """

    UNKNOWN = auto()

    ACCUMULATION = auto()

    REACCUMULATION = auto()

    MARKUP = auto()

    DISTRIBUTION = auto()

    REDISTRIBUTION = auto()

    MARKDOWN = auto()



# =============================================================================
# Generic percentile buckets Used by both Spread and Volume classifiers.
# =============================================================================
class ClassificationBucket(IntEnum):
    ULTRA_LOW = auto()
    VERY_LOW = auto()
    LOW = auto()
    AVERAGE = auto()    
    HIGH = auto()
    VERY_HIGH = auto()
    ULTRA_HIGH = auto()


# =============================================================================
# Comparison checker
# =============================================================================
class Comparison(IntEnum):
    LOWER = -1
    EQUAL = 0
    HIGHER = 1

# =============================================================================
# TrendQuality
# =============================================================================

""" class TrendQuality(StrEnum):
    VERY_WEAK = auto()
    WEAK = auto()
    NEUTRAL = auto()
    STRONG = auto()
    VERY_STRONG = auto()
 """

class BackgroundBias(IntEnum):

    VERY_BEARISH = 1

    BEARISH = 2

    NEUTRAL = 3

    BULLISH = 4

    VERY_BULLISH = 5

class StructuralPattern(IntEnum):

    UNKNOWN = 0

    IMPROVING = 1

    STABLE = 2

    WEAKENING = 3

    BREAKING = 4


class ProfessionalProgression(IntEnum):
    """Change in professional structural quality over time."""

    UNKNOWN = 0
    IMPROVING = 1
    STABLE = 2
    WEAKENING = 3


# =============================================================================
# BAR CLASSIFICATION
# =============================================================================

@dataclass(slots=True)
class BarClassification:

    direction: Direction

    volume: VolumeClass

    spread: SpreadClass

    close_position: ClosePosition



# =============================================================================
# SIGNAL RESULT
# =============================================================================

@dataclass(slots=True)
class SignalResult:

    signal: SignalType

    confidence: int

    description: str


# =============================================================================
#                               Weekly Metrics 
# =============================================================================


# =============================================================================
#                               Swing Models
# =============================================================================


# =============================================================================
# Swing 
# =============================================================================

# SwingCandidate class here



@dataclass(slots=True, frozen=True)
class Swing:
    """
    Represents one confirmed market swing.
    """

    type: SwingType

    price: float

    bar_index: int                 # Pivot bar

    confirmation_index: int        # Bar where the reversal was confirmed

    week_beginning: str
    
    metrics_index: int | None = None             # Row in metrics dataframe    

    label: SwingLabel | None = None

    def __post_init__(self) -> None:

        if self.metrics_index is None:
            object.__setattr__(
                self,
                "metrics_index",
                self.bar_index,
            )

        if self.bar_index < 0:
            raise ValueError(
                "bar_index cannot be negative."
            )

        if self.confirmation_index < self.bar_index:
            raise ValueError(
                "confirmation_index must be >= bar_index."
            )

        if self.price <= 0:
            raise ValueError(
                "price must be positive."
            )

        if not self.week_beginning:
            raise ValueError(
                "week_beginning cannot be empty."
            )


@dataclass(slots=True, frozen=True)
class ClassifiedSwing:
    """
    A confirmed swing with its structural classification.

    Produced by the Trend Engine after comparing confirmed
    swings of the same type.
    """

    swing: Swing

    label: SwingLabel | None
    
    @property
    def type(self) -> SwingType:
        return self.swing.type

    @property
    def price(self) -> float:
        return self.swing.price

    @property
    def week_beginning(self) -> str:
        return self.swing.week_beginning


@dataclass(slots=True, frozen=True)
class StructuralSwingScore:
    """
    Professional Swing Score (PSS).

    Every component is normalized to the range
    0.0 → 1.0.
    """

    price: float

    structural_size: float

    duration: float

    volume: float

    spread: float    

    overall: float
    
@dataclass(slots=True, frozen=True)
class StructuralSwingEvaluation:

    score: StructuralSwingScore

    snapshot: SwingHistorySnapshot



@dataclass(slots=True, frozen=True)
class SwingHistory:

    swings: tuple[Swing, ...]

    current_index: int 
    

@dataclass(slots=True, frozen=True)
class SwingHistorySnapshot:

    current_amplitude: float

    current_duration: int

    current_spread_adjusted_amplitude: float | None

    amplitudes: tuple[float, ...]

    spread_adjusted_amplitudes: tuple[float, ...]

    durations: tuple[int, ...]

    volumes: tuple[float, ...]

    spreads: tuple[float, ...]


@dataclass(slots=True, frozen=True)
class SwingMetricSnapshot:
    """
    Immutable metric values for the current swing.
    """

    volume: float

    spread: float

    avg_volume: float

    avg_spread: float


@dataclass(slots=True, frozen=True)
class SwingContext:

    swing: Swing

    history: SwingHistorySnapshot    

    metrics: SwingMetricSnapshot

    trend: TrendStructure | None = None

    evidence: EvidenceResult | None = None

@dataclass(slots=True, frozen=True)
class SwingProfessionalEvaluation:
    structure: StructuralSwingEvaluation
    smart_money: SmartMoneyScore
    professional: SwingProfessionalScore

# =============================================================================
# StructuralSwing
# =============================================================================

@dataclass(slots=True, frozen=True)
class StructuralSwing:
    """
    Structurally significant swing.
    """

    swing: Swing

    evaluation: SwingProfessionalEvaluation

    grade: SwingGrade

    is_failed: bool = False


@dataclass(slots=True, frozen=True)
class StructuralBackground:

    observations: tuple[Evidence, ...]

    strength: float

    confidence: float

# =============================================================================
#                             Trend Models
# =============================================================================
 
# =============================================================================
# TrendStructure
# =============================================================================

@dataclass(slots=True, frozen=True)
class TrendStructure:
    """
    Structural interpretation of the confirmed swing sequence.

    Produced by the TrendAnalyzer after swing classification and
    consumed by the Trend strength measurement, Background Engine,
    Wyckoff Engine, Scanner, and Report Generator.
    """

    direction: TrendDirection

    state: TrendState

    strength: float

    confidence: float

    swing_count: int

    swings: tuple[ClassifiedSwing, ...]
    
    structural_swings: tuple[StructuralSwing, ...]

    hh_count: int

    hl_count: int

    lh_count: int

    ll_count: int
    
    # ---------------------------------------------------------
    # Convenience Properties
    # ---------------------------------------------------------

    @property
    def is_uptrend(self) -> bool:
        return self.direction == TrendDirection.UP

    @property
    def is_downtrend(self) -> bool:
        return self.direction == TrendDirection.DOWN

    @property
    def is_range(self) -> bool:
        return self.direction == TrendDirection.RANGE

    @property
    def is_healthy(self) -> bool:
        return self.state == TrendState.HEALTHY

    @property
    def is_reversing(self) -> bool:
        return self.state == TrendState.REVERSING
    
    @property
    def is_developing(self) -> bool:
        return self.state == TrendState.DEVELOPING

    @property
    def is_correcting(self) -> bool:
        return self.state == TrendState.CORRECTING

    @property
    def is_exhausted(self) -> bool:
        return self.state == TrendState.EXHAUSTED

    @property
    def bullish_swings(self) -> int:
        return self.hh_count + self.hl_count

    @property
    def bearish_swings(self) -> int:
        return self.lh_count + self.ll_count
 
 
# =============================================================================
# TrendResult
# =============================================================================

@dataclass(slots=True, frozen=True)
class TrendResult:
    """
    Output of TrendAnalyzer.
    """
    structure: TrendStructure

    @property
    def direction(self):
        return self.structure.direction

    @property
    def state(self):
        return self.structure.state

    @property
    def strength(self):
        return self.structure.strength

    @property
    def confidence(self):
        return self.structure.confidence

    @property
    def hh_count(self):
        return self.structure.hh_count

    @property
    def hl_count(self):
        return self.structure.hl_count

    @property
    def lh_count(self):
        return self.structure.lh_count

    @property
    def ll_count(self):
        return self.structure.ll_count

    @property
    def swing_count(self):
        return self.structure.swing_count

    @property
    def swings(self):
        return self.structure.swings
    
    
# =============================================================================
#                               Background Models
# =============================================================================
@dataclass(slots=True, frozen=True)
class Requirement:
    """
    Result of evaluating one detector rule.
    """

    name: str

    passed: bool

    mandatory: bool = True

    message: str | None = None
    
    
# =============================================================================
# VSA Context
# =============================================================================

@dataclass(slots=True, frozen=True)
class VSAContext:
    """Independent market context consumed by VSA event logic."""

    trend_direction: TrendDirection
    trend_state: TrendState
    trend_strength: float
    trend_confidence: float

    structural_pattern: StructuralPattern

    professional_progression: ProfessionalProgression
    professional_score: float | None

    stopping_volume: float | None
    climactic_volume: float | None


# =============================================================================
# Background Context
# =============================================================================

@dataclass(slots=True, frozen=True)
class BarContext:
    """
    Semantic representation of a single market bar.

    Used by the Evidence Engine to avoid repeated
    DataFrame lookups.
    """
    
    week_beginning: str

    # ----------------------------------------
    # Position
    # ----------------------------------------     
    
    bar_index: int

    # ----------------------------------------
    # Semantic classifications
    # ----------------------------------------

    spread: SpreadClass

    volume: VolumeClass

    direction: Direction

    close_position: ClosePosition

    # ----------------------------------------
    # Normalized metrics
    # ----------------------------------------

    spread_ratio: float

    volume_ratio: float

    
    # ----------------------------------------
    # Price
    # ----------------------------------------

    open: float

    high: float

    low: float

    close_price: float

    # ----------------------------------------
    # Derived bar geometry
    # ----------------------------------------

    body: float

    upper_shadow: float

    lower_shadow: float

    close_ratio: float

    # ----------------------------------------
    # Previous price only
    # ----------------------------------------

    prev_high: float

    prev_low: float

    prev_close: float    

    prev_spread: float    
    
    
    @property
    def closes_in_upper_half(self) -> bool:
        return self.close_ratio >= 0.50
    
    @property
    def rejects_lows(self) -> bool:
        return self.close_ratio >= 0.60
    
    @property
    def is_narrow_spread(self) -> bool:
        import config
        return (
            self.spread_ratio
            <= config.NARROW_SPREAD_RATIO
        )


    @property
    def is_wide_spread(self) -> bool:
        import config
        return (
            self.spread_ratio
            >= config.WIDE_SPREAD_RATIO
        )


    @property
    def is_very_wide_spread(self) -> bool:
        import config
        return (
            self.spread_ratio
            >= config.VERY_WIDE_SPREAD_RATIO
        )
    
    @property
    def spread_size(self) -> float:
        return self.high - self.low

    @property
    def is_up_bar(self) -> bool:
        return self.direction == Direction.UP

    @property
    def is_down_bar(self) -> bool:
        return self.direction == Direction.DOWN

    @property
    def is_neutral_bar(self) -> bool:
        return self.direction == Direction.NEUTRAL

    @property
    def closes_on_high(self) -> bool:
        return self.close_position == ClosePosition.ON_HIGH

    @property
    def closes_on_low(self) -> bool:
        return self.close_position == ClosePosition.ON_LOW

    @property
    def midpoint(self) -> float:
        return (self.high + self.low) / 2


@dataclass(slots=True, frozen=True)
class BackgroundContext:
    """
    Immutable context shared by all Background/Evidence collectors.

    This object provides:
        • Current bar
        • Previous bar
        • Recent rolling history
        • Longer background history
        • Trend structure

    It allows every collector to operate without directly
    accessing the Metrics Engine or DataFrame outside the
    supplied context.
    """
    
    # ---------------------------------------------------------
    # Historical data
    # ---------------------------------------------------------

    background: pd.DataFrame
    """
    Long-term historical window used for market background,
    percentile comparisons and Wyckoff phase detection.
    """

    recent: pd.DataFrame
    """
    Recent bars used by short-term VSA rules.
    Typically the last 5–10 bars.
    """

    # ---------------------------------------------------------
    # Trend
    # ---------------------------------------------------------

    trend: TrendStructure
    
    
    # ----------------------------------------
    # Recent background bars
    # ----------------------------------------
    
    bars: tuple[BarContext, ...]
    

    # ---------------------------------------------------------
    # Current bar contexts
    # ---------------------------------------------------------

    current: BarContext

    previous: BarContext | None

    structural_swings: tuple[StructuralSwing, ...]

    structural_pattern: StructuralPattern

    vsa_context: VSAContext
    
    # ---------------------------------------------------------
    # Convenience helpers
    # ---------------------------------------------------------
    def is_bullish_environment(self) -> bool:
        return (
            self.trend.direction
            == TrendDirection.UP
        )


    def is_bearish_environment(self) -> bool:
        return (
            self.trend.direction
            == TrendDirection.DOWN
        )
        
    @property
    def latest_structural_swing(
        self,
    ) -> StructuralSwing | None:
        if not self.structural_swings:
            return None

        return self.structural_swings[-1]
    
    @property
    def latest_professional_evaluation(
        self,
    ) -> SwingProfessionalEvaluation | None:

        latest = self.latest_structural_swing

        if latest is None:
            return None

        return latest.evaluation
        
    @property
    def has_previous(self) -> bool:
        """True when a previous bar exists."""
        return self.previous is not None

    @property
    def has_background(self) -> bool:
        """True if the background window is populated."""
        return not self.background.empty
    
    @property
    def has_recent(self) -> bool:
        """True if the recent window is populated."""
        return not self.recent.empty  
    
    
    @property
    def background_size(self) -> int:
        """Number of bars in the background window."""
        return len(self.background)

    @property
    def recent_size(self) -> int:
        """Number of bars in the recent window."""
        return len(self.recent)
          
    
    # @property
    # def oldest(self) -> pd.Series:
    #     """Oldest bar in the background window."""
    #     if self.background.empty:
    #         raise ValueError(
    #             "Background window is empty.",
    #         )

    #     return self.background.iloc[0]

    # @property
    # def newest(self) -> pd.Series:
    #     """Most recent bar in the background window."""
    #     if self.background.empty:
    #         raise ValueError(
    #             "Background window is empty.",
    #         )

    #     return self.background.iloc[-1]
   

    # @property
    # def oldest_recent(self) -> pd.Series:
    #     if self.recent.empty:
    #         raise ValueError(
    #             "Recent window is empty.",
    #         )

    #     return self.recent.iloc[0]
      
       
    # @property
    # def newest_recent(self) -> pd.Series:
    #     """
    #     Most recent bar in the recent window.
    #     """
    #     if self.recent.empty:
    #         raise ValueError(
    #             "Recent window is empty.",
    #         )

    #     return self.recent.iloc[-1]
    
   
        
    def with_current(
        self,
        index: int,
    ) -> "BackgroundContext":
        """
        Return a new context whose current bar is the
        requested bar in self.bars.
        """

        if index <= 0:
            raise ValueError(
                "index must be greater than zero."
            )

        if index >= len(self.bars):
            raise IndexError(index)

        return replace(
            self,
            current=self.bars[index],
            previous=self.bars[index - 1],
        )  
   
# =============================================================================
# EVIDENCE 
# =============================================================================

@dataclass(slots=True, frozen=True)
class Evidence:
    """
    A single piece of VSA evidence.

    Evidence objects are immutable and form the
    foundation of the background analysis.
    
    Every detector contributes Evidence objects.
    The Background Engine aggregates them into a
    professional market opinion.
    """

    code: EvidenceCode

    category: EvidenceCategory

    direction: EvidenceDirection
    
    strength: float

    weight: float

    observation: str

    description: str    

    bar_index: int

    week_beginning: str
    
    test_index: int | None = None

    recovery_index: int | None = None
    
    quality: float = 1.0

@dataclass(frozen=True, slots=True)
class AggregatedEvidenceEvent:
    bar_index: int
    direction: EvidenceDirection
    evidences: tuple[Evidence, ...]
    codes: tuple[EvidenceCode, ...]
    primary_codes: tuple[EvidenceCode, ...]
    supporting_codes: tuple[EvidenceCode, ...]
    effort_result_codes: tuple[EvidenceCode, ...]
    structural_codes: tuple[EvidenceCode, ...]

    contribution: float


# =============================================================================
# BACKGROUND RESULTS 
# =============================================================================

    
@dataclass(slots=True, frozen=True)
class SmartMoneyEvidence:
    """
    Represents one confirmed Smart Money observation
    produced by the Evidence Engine.
    """

    code: EvidenceCode

    category: EvidenceCategory

    direction: EvidenceDirection

    strength: EvidenceStrength

    confidence: float

    weight: float

    metrics_index: int    

    description: str

    swing_index: int | None = None

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                "confidence must be between 0 and 1."
            )

        if self.weight < 0:
            raise ValueError(
                "weight must be non-negative."
            )        
       
@dataclass(slots=True, frozen=True)
class SmartMoneyScore:
    """
    Smart Money activity detected inside a swing.
    """

    stopping_volume: float

    stopping_breakdown: ScoreBreakdown

    climactic_volume: float

    climactic_breakdown: ScoreBreakdown

    overall: float
    

@dataclass(slots=True, frozen=True)
class SwingProfessionalScore:

    structure: StructuralSwingScore

    smart_money: SmartMoneyScore

    overall: float

    @classmethod
    def create(
        cls,
        structure: StructuralSwingScore,
        smart_money: SmartMoneyScore,
    ) -> "SwingProfessionalScore":

        import config

        components = (
            component(
                structure.overall,
                config.PROFESSIONAL_STRUCTURE_WEIGHT,
            ),
            component(
                smart_money.overall,
                config.PROFESSIONAL_SMART_MONEY_WEIGHT,
            ),
        )

        overall = combine_scores(
            components,
        )

        return cls(
            structure=structure,
            smart_money=smart_money,
            overall=overall,
        )

@dataclass(slots=True, frozen=True)
class SmartMoneyBar:

    high: float
    low: float
    open: float
    close: float

    spread: float
    avg_spread: float

    volume: float
    avg_volume: float

    @property
    def volume_ratio(self) -> float:
        """
        Current volume relative to average volume.
        """

        if self.avg_volume <= 0:
            return 0.0

        return self.volume / self.avg_volume

    @property
    def spread_ratio(self) -> float:
        """
        Current spread relative to average spread.
        """

        if self.avg_spread <= 0:
            return 0.0

        return self.spread / self.avg_spread

    @property
    def close_position(self) -> float:
        """
        Relative closing position within the bar.

        0.0 = close at the low
        1.0 = close at the high
        """

        if self.spread <= 0:
            return 0.5

        return (
            self.close - self.low
        ) / self.spread

    @property
    def lower_tail_ratio(self) -> float:
        """
        Lower tail as a proportion of the total spread.
        """

        if self.spread <= 0:
            return 0.0

        lower_tail = (
            min(self.open, self.close)
            - self.low
        )

        return lower_tail / self.spread

    @property
    def extreme_close_position(self) -> float:
        return max(
            self.close_position,
            1.0 - self.close_position,
        )


@dataclass(slots=True, frozen=True)
class SmartMoneySnapshot:

    bars: tuple[SmartMoneyBar, ...]


@dataclass(slots=True, frozen=True)
class ScoreBreakdown:

    overall: float

    components: tuple[ScoreComponent, ...]

    @classmethod
    def empty(cls) -> "ScoreBreakdown":
        return cls(
            overall=0.0,
            components=(),
        )

@dataclass(frozen=True, slots=True)
class EvidenceDefinition:

    category: EvidenceCategory

    direction: EvidenceDirection

    strength: float

    weight: float

    observation: str

    description: str


@dataclass(slots=True, frozen=True)
class BackgroundAssessment:

    supply: float

    demand: float

    professional: float

    overall: float

    bias: BackgroundBias
    
    confidence: float   

    evidence: tuple[Evidence, ...]

    summary: str 

    def is_bullish(self) -> bool:
        return self.bias in (
            BackgroundBias.BULLISH,
            BackgroundBias.VERY_BULLISH,
        )

    def is_bearish(self) -> bool:
        return self.bias in (
            BackgroundBias.BEARISH,
            BackgroundBias.VERY_BEARISH,
        )

    def is_neutral(self) -> bool:
        return self.bias == BackgroundBias.NEUTRAL
    

@dataclass(slots=True, frozen=True)
class EvidenceScore:

    supply: float = 0.0

    demand: float = 0.0

    professional: float = 0.0


@dataclass(slots=True, frozen=True)
class EvidenceSummary:

    bullish: tuple[Evidence, ...]

    bearish: tuple[Evidence, ...]

    bullish_score: float

    bearish_score: float
    
    bullish_count: int
    bearish_count: int
    total_count: int

    net_score: float

    bias: MarketBias

# =============================================================================
# COMPLETE ANALYSIS
# =============================================================================

@dataclass(slots=True)
class AnalysisResult:

    symbol: str

    background: EvidenceResult

    signal: SignalResult | None

    interpretation: str






