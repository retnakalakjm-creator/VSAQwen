from __future__ import annotations

from pydantic import BaseModel


class BarDTO(BaseModel):
    bar_index: int
    week: str
    open: float
    high: float
    low: float
    close: float
    volume: float


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
    bar_index: int
    confirmation_index: int
    week: str
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


class AnalysisDTO(BaseModel):
    symbol: str
    timeframe: str
    latest_bar_index: int
    latest_week: str
    bars: list[BarDTO]
    trend: TrendDTO
    structural_swings: list[StructuralSwingDTO]
    evidence: list[EvidenceDTO]
    qualification: QualificationDTO
    professional: ProfessionalScoreDTO


class HealthDTO(BaseModel):
    status: str
    service: str
