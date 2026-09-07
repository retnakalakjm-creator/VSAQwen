from __future__ import annotations

import pandas as pd

from data import daily_to_weekly, download_data
from metrics_engine import MetricsEngine
from scanner import ScannerCandidate, ScannerEngine

from .schemas import (
    AnalysisDTO,
    BarDTO,
    EvidenceDTO,
    HealthDTO,
    ProfessionalScoreDTO,
    QualificationDTO,
    StructuralSwingDTO,
    SwingScoreDTO,
    TrendDTO,
)


class ProVSAService:
    """Thin API adapter over the existing authoritative ProVSA engine."""

    def analyze_symbol(self, symbol: str) -> AnalysisDTO:
        symbol = symbol.strip().upper()
        if not symbol:
            raise ValueError("symbol is required")

        daily = download_data(symbol)
        weekly = daily_to_weekly(daily)
        metrics = MetricsEngine().calculate(weekly)

        scanner = ScannerEngine()
        target_index = len(metrics) - 1
        candidate = scanner.scan_to_index(metrics, target_index)
        trend = candidate.evidence.context.trend

        labels = {
            (item.swing.type, item.swing.bar_index): item.label.value
            if item.label is not None else None
            for item in trend.swings
        }

        return AnalysisDTO(
            symbol=symbol,
            timeframe="1W",
            latest_bar_index=target_index,
            latest_week=str(weekly.iloc[target_index]["week_beginning"]),
            bars=[self._bar(row, index) for index, (_, row) in enumerate(weekly.iterrows())],
            trend=TrendDTO(
                direction=trend.direction.value,
                state=trend.state.value,
                strength=float(trend.strength),
                confidence=float(trend.confidence),
                swing_count=trend.swing_count,
                hh_count=trend.hh_count,
                hl_count=trend.hl_count,
                lh_count=trend.lh_count,
                ll_count=trend.ll_count,
            ),
            structural_swings=[self._structural_swing(item, labels) for item in trend.structural_swings],
            evidence=[self._evidence(item) for item in candidate.evidence.evidence],
            qualification=QualificationDTO(
                qualification=candidate.qualification.value,
                actionable=candidate.actionable,
                reason=candidate.reason,
                evidence_codes=list(candidate.qualification_result.evidence_codes),
                evidence_bar_indices=list(candidate.qualification_result.evidence_bar_indices),
            ),
            professional=ProfessionalScoreDTO(
                trend=float(candidate.professional.trend),
                supply=float(candidate.professional.supply),
                demand=float(candidate.professional.demand),
                effort=float(candidate.professional.effort),
                strength=float(candidate.professional.strength),
                weakness=float(candidate.professional.weakness),
                net_strength=float(candidate.net_strength),
                net_pressure=float(candidate.net_pressure),
                confidence=float(candidate.confidence),
            ),
        )

    @staticmethod
    def _bar(row: pd.Series, index: int) -> BarDTO:
        return BarDTO(
            bar_index=index,
            week=str(row["week_beginning"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
        )

    @staticmethod
    def _evidence(item) -> EvidenceDTO:
        return EvidenceDTO(
            code=item.code.value,
            category=item.category.name,
            direction=item.direction.name,
            strength=float(item.strength),
            weight=float(item.weight),
            quality=float(item.quality),
            observation=item.observation,
            description=item.description,
            bar_index=item.bar_index,
            week=str(item.week_beginning),
            test_index=item.test_index,
            recovery_index=item.recovery_index,
        )

    @staticmethod
    def _structural_swing(item, labels) -> StructuralSwingDTO:
        swing = item.swing
        score = item.evaluation.professional
        structure = score.structure
        smart_money = score.smart_money
        label = labels.get((swing.type, swing.bar_index))
        return StructuralSwingDTO(
            bar_index=swing.bar_index,
            confirmation_index=swing.confirmation_index,
            week=str(swing.week_beginning),
            type=swing.type.value,
            label=label,
            price=float(swing.price),
            grade=item.grade.name,
            is_failed=item.is_failed,
            score=SwingScoreDTO(
                price=float(structure.price),
                structural_size=float(structure.structural_size),
                duration=float(structure.duration),
                volume=float(structure.volume),
                spread=float(structure.spread),
                overall=float(structure.overall),
                smart_money=float(smart_money.overall),
                professional=float(score.overall),
            ),
        )

    @staticmethod
    def health() -> HealthDTO:
        return HealthDTO(status="ok", service="provsa-api")
