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


class WeeklyBarReadingDTO(BaseModel):
    week: str
    professional_reading: str


class WeeklyBarReadingsResponseDTO(BaseModel):
    symbol: str
    timeframe: str
    latest_week: str
    lookback: int
    readings: list[WeeklyBarReadingDTO]


class TradePlanLevelDTO(BaseModel):
    label: str
    price: float | None
    lower: float | None
    upper: float | None
    source: str
    note: str


class TradePlanDTO(BaseModel):
    posture: str
    setup_type: str
    reference_price: float | None
    support: TradePlanLevelDTO
    resistance: TradePlanLevelDTO
    entry_condition: str
    confirmation_trigger: str
    invalidation_condition: str
    risk_reading: str
    reward_reading: str
    notes: list[str]
    analysis_only: bool = True


class TradePlanResponseDTO(BaseModel):
    symbol: str
    timeframe: str
    latest_week: str
    plan: TradePlanDTO


class VSAEventAuditRowDTO(BaseModel):
    symbol: str
    replay_bar_index: int
    replay_week: str
    event_count: int
    target_event_codes: list[str]
    scoring_event_codes: list[str]
    qualifying_event_codes: list[str]
    campaign_event_codes: list[str]
    structural_event_codes: list[str]
    vsa_event_codes: list[str]
    qualification: str
    actionable: bool
    used_fallback_evidence: bool
    scoring_evidence_age: int | None
    net_pressure: float
    confidence: float
    audit_flags: list[str]
    detector_diagnostics: list[str]
    notes: list[str]


class VSAEventAuditSymbolResultDTO(BaseModel):
    symbol: str
    timeframe: str
    start_week: str | None
    end_week: str | None
    replay_weeks: int
    rows: list[VSAEventAuditRowDTO]
    audit_only: bool = True


class VSAEventAuditResponseDTO(BaseModel):
    symbols: list[str]
    timeframe: str
    start_week: str | None
    end_week: str | None
    horizon_weeks: int
    results: list[VSAEventAuditSymbolResultDTO]
    errors: dict[str, str] = Field(default_factory=dict)
    audit_only: bool = True


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


class DataSourceStatusDTO(BaseModel):
    symbol: str
    configured_provider: str
    active_provider: str
    cache_available: bool
    cache_source: str | None
    cache_format: str | None
    cache_rows: int | None
    cache_first_date: str | None
    cache_last_date: str | None
    cache_updated_at_utc: str | None
    stale_cache: bool
    stale_reason: str | None
    upstox_enabled: bool | None
    upstox_token_env: str | None
    upstox_token_present: bool | None
    upstox_symbol_mapped: bool | None
    diagnostic_only: bool = True
    cache_metadata: dict[str, object] | None = None


class HealthDTO(BaseModel):
    status: str
    service: str
