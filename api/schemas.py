from __future__ import annotations

from pydantic import BaseModel, Field


class BarDTO(BaseModel):
    bar_index: int
    week: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    price_gap_ratio: float | None = None
    price_anomaly: bool = False
    volume_anomaly: bool = False
    corporate_action_anomaly: bool = False


class SwingScoreDTO(BaseModel):
    price: float
    structural_size: float
    duration: float
    volume: float
    spread: float
    overall: float
    smart_money: float
    professional: float


class StructuralSwingDTO(BaseModel):
    # Backward-compatible aliases. `bar_index` and `week` refer to the pivot.
    bar_index: int
    confirmation_index: int
    week: str

    # Explicit causal timing fields.
    pivot_bar_index: int
    pivot_week: str
    confirmation_bar_index: int
    confirmation_week: str

    type: str
    label: str | None
    price: float
    grade: str
    is_failed: bool
    score: SwingScoreDTO


class EvidenceDTO(BaseModel):
    code: str
    category: str
    direction: str
    strength: float
    weight: float
    quality: float
    observation: str
    description: str
    bar_index: int
    week: str
    test_index: int | None
    recovery_index: int | None


class TrendDTO(BaseModel):
    direction: str
    state: str
    strength: float
    confidence: float
    swing_count: int
    hh_count: int
    hl_count: int
    lh_count: int
    ll_count: int


class QualificationDTO(BaseModel):
    qualification: str
    actionable: bool
    reason: str
    evidence_codes: list[str]
    evidence_bar_indices: list[int]


class ProfessionalScoreDTO(BaseModel):
    trend: float
    supply: float
    demand: float
    effort: float
    strength: float
    weakness: float
    net_strength: float
    net_pressure: float
    confidence: float


class DecisionContextEventDTO(BaseModel):
    bar_index: int
    week: str
    code: str
    category: str
    direction: str
    strength: float
    quality: float
    observation: str
    description: str
    role: str


class StructuralSwingMemoryDTO(BaseModel):
    pivot_bar_index: int
    confirmation_bar_index: int
    pivot_week: str
    type: str
    label: str | None
    price: float
    grade: str
    is_failed: bool
    score: float | None


class VSAStorySummaryDTO(BaseModel):
    headline: str
    summary: str
    confirmation_condition: str
    invalidation_condition: str
    what_to_expect_next: list[str]


class DecisionContextDTO(BaseModel):
    schema_version: int
    symbol: str
    timeframe: str
    mode: str
    latest_bar_index: int | None
    latest_week: str | None
    qualification: str
    actionable: bool
    decision: str
    tradability: str
    phase: str
    bias: str
    confidence: float
    net_strength: float
    net_pressure: float
    reason: str
    recent_events: list[DecisionContextEventDTO]
    structural_swings: list[StructuralSwingMemoryDTO]
    story: VSAStorySummaryDTO
    evaluated_at_utc: str


class DecisionJournalEntryDTO(BaseModel):
    schema_version: int
    entry_id: str
    symbol: str
    timeframe: str
    source_context_week: str | None
    source_context_bar_index: int | None
    source_context_evaluated_at_utc: str
    created_at_utc: str
    phase: str
    bias: str
    tradability: str
    decision: str
    confidence: float
    net_pressure: float
    headline: str
    summary: str
    confirmation_condition: str
    invalidation_condition: str
    expected_next_behavior: list[str]
    support_price: float | None
    resistance_price: float | None
    reference_price: float | None
    status: str


class DecisionJournalDTO(BaseModel):
    symbol: str
    timeframe: str
    entries: list[DecisionJournalEntryDTO]


class DecisionJournalEvaluationDTO(BaseModel):
    entry_id: str
    symbol: str
    timeframe: str
    source_context_week: str | None
    source_context_bar_index: int | None
    outcome: str
    checked_bars: int
    first_checked_week: str | None
    last_checked_week: str | None
    confirmation_hit: bool
    invalidation_hit: bool
    favorable_move_pct: float | None
    adverse_move_pct: float | None
    notes: str


class DecisionJournalEvaluationResponseDTO(BaseModel):
    symbol: str
    timeframe: str
    horizon_bars: int
    latest_week: str
    persist_status: bool = False
    evaluations: list[DecisionJournalEvaluationDTO]


class AnalysisDTO(BaseModel):
    symbol: str
    timeframe: str
    latest_bar_index: int
    latest_week: str
    bars: list[BarDTO]
    anomaly_bar_indices: list[int] = Field(default_factory=list)
    signal_bar_anomaly: bool = False
    signal_bar_anomaly_reason: str | None = None
    trend: TrendDTO
    structural_swings: list[StructuralSwingDTO]
    evidence: list[EvidenceDTO]
    qualification: QualificationDTO
    professional: ProfessionalScoreDTO
    decision_context: DecisionContextDTO | None = None


class HealthDTO(BaseModel):
    status: str
    service: str