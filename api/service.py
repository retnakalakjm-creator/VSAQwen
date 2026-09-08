from __future__ import annotations

from pathlib import Path

import pandas as pd

from data import completed_weekly_only, daily_to_weekly, download_data
from decision_context import DecisionContext, DecisionContextStore, build_decision_context
from engine.columns import (
    COL_CORPORATE_ACTION_ANOMALY,
    COL_PRICE_ANOMALY,
    COL_PRICE_GAP_RATIO,
    COL_VOLUME_ANOMALY,
)
from metrics_engine import MetricsEngine
from production_scanner import scan_latest_candidate_production
from scanner_state import ScannerStateStore

from .schemas import (
    AnalysisDTO,
    BarDTO,
    DecisionContextDTO,
    EvidenceDTO,
    HealthDTO,
    ProfessionalScoreDTO,
    QualificationDTO,
    StructuralSwingDTO,
    SwingScoreDTO,
    TrendDTO,
)


DEFAULT_API_TIMEFRAME = "1W"


class ProVSAService:
    """Thin API adapter over the existing authoritative ProVSA engine."""

    def __init__(
        self,
        decision_context_store: DecisionContextStore | None = None,
        scanner_state_store: ScannerStateStore | None = None,
        *,
        scanner_state_root: str | Path = "state",
        allow_full_replay_fallback: bool = True,
        persist_decision_context: bool = True,
    ) -> None:
        self._decision_context_store = decision_context_store or DecisionContextStore()
        self._scanner_state_store = scanner_state_store
        self._scanner_state_root = scanner_state_root
        self._allow_full_replay_fallback = allow_full_replay_fallback
        self._persist_decision_context = persist_decision_context

    def analyze_symbol(self, symbol: str) -> AnalysisDTO:
        symbol = self._normalize_symbol(symbol)
        weekly = self._completed_weekly_for_symbol(symbol)
        return self._analyze_symbol_from_weekly(symbol, weekly)

    def decision_context_for_symbol(self, symbol: str) -> DecisionContextDTO:
        """Return cached decision context when no new completed week exists.

        This endpoint is intentionally narrower than full analysis. It checks the
        latest completed weekly bar identity, returns the saved compact context
        when it is still current, and only falls back to scanner analysis when
        the context is missing, invalid, developing-mode, or stale.
        """
        symbol = self._normalize_symbol(symbol)
        weekly = self._completed_weekly_for_symbol(symbol)
        latest_week = self._latest_week(weekly)

        cached = self._load_cached_decision_context(symbol)
        if (
            cached is not None
            and cached.timeframe == DEFAULT_API_TIMEFRAME
            and cached.mode.value == "confirmed"
            and cached.latest_week == latest_week
        ):
            return self._decision_context_dto(cached)

        analysis = self._analyze_symbol_from_weekly(symbol, weekly)
        if analysis.decision_context is None:
            raise ValueError("analysis did not produce a decision context")
        return analysis.decision_context

    def _analyze_symbol_from_weekly(
        self,
        symbol: str,
        weekly: pd.DataFrame,
    ) -> AnalysisDTO:
        metrics = MetricsEngine().calculate(weekly)

        timeframe = DEFAULT_API_TIMEFRAME
        target_index = len(metrics) - 1
        candidate = scan_latest_candidate_production(
            metrics,
            symbol=symbol,
            timeframe=timeframe,
            state_store=self._scanner_state_store,
            state_root=self._scanner_state_root,
            allow_full_replay_fallback=self._allow_full_replay_fallback,
        )
        if candidate is None:
            raise ValueError(
                "not enough completed weekly bars to analyze symbol through "
                "the production scanner path"
            )

        trend = candidate.evidence.context.trend
        decision_context = build_decision_context(
            candidate,
            symbol=symbol,
            timeframe=timeframe,
        )
        if self._persist_decision_context:
            self._decision_context_store.save(decision_context)

        labels = {
            (item.swing.type, item.swing.bar_index): item.label.value
            if item.label is not None else None
            for item in trend.swings
        }

        return AnalysisDTO(
            symbol=symbol,
            timeframe=timeframe,
            latest_bar_index=target_index,
            latest_week=str(metrics.iloc[target_index]["week_beginning"]),
            bars=[self._bar(row, index) for index, (_, row) in enumerate(metrics.iterrows())],
            anomaly_bar_indices=self._anomaly_bar_indices(metrics),
            signal_bar_anomaly=bool(getattr(candidate, "signal_bar_anomaly", False)),
            signal_bar_anomaly_reason=getattr(candidate, "signal_bar_anomaly_reason", None),
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
            structural_swings=[
                self._structural_swing(item, labels, metrics)
                for item in trend.structural_swings
            ],
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
            decision_context=self._decision_context_dto(decision_context),
        )

    def _completed_weekly_for_symbol(self, symbol: str) -> pd.DataFrame:
        daily = download_data(symbol)
        weekly = completed_weekly_only(daily_to_weekly(daily))
        if weekly.empty:
            raise ValueError("no completed weekly bars are available for symbol")
        return weekly

    def _load_cached_decision_context(self, symbol: str) -> DecisionContext | None:
        try:
            return self._decision_context_store.load(symbol, DEFAULT_API_TIMEFRAME)
        except (FileNotFoundError, ValueError):
            return None

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        normalized = symbol.strip().upper()
        if not normalized:
            raise ValueError("symbol is required")
        return normalized

    @staticmethod
    def _latest_week(weekly: pd.DataFrame) -> str:
        if weekly.empty:
            raise ValueError("no completed weekly bars are available")
        return str(weekly.iloc[len(weekly) - 1]["week_beginning"])

    @staticmethod
    def _decision_context_dto(context: DecisionContext) -> DecisionContextDTO:
        return DecisionContextDTO(**context.to_dict())

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
            price_gap_ratio=ProVSAService._optional_float(row, COL_PRICE_GAP_RATIO),
            price_anomaly=ProVSAService._bool_flag(row, COL_PRICE_ANOMALY),
            volume_anomaly=ProVSAService._bool_flag(row, COL_VOLUME_ANOMALY),
            corporate_action_anomaly=ProVSAService._bool_flag(
                row,
                COL_CORPORATE_ACTION_ANOMALY,
            ),
        )

    @staticmethod
    def _week_at(bars: pd.DataFrame, index: int) -> str:
        if index < 0 or index >= len(bars):
            raise IndexError("swing index is outside weekly bars")
        return str(bars.iloc[index]["week_beginning"])

    @staticmethod
    def _optional_float(row: pd.Series, column: str) -> float | None:
        if column not in row:
            return None
        value = row[column]
        if pd.isna(value):
            return None
        return float(value)

    @staticmethod
    def _bool_flag(row: pd.Series, column: str) -> bool:
        if column not in row:
            return False
        value = row[column]
        if pd.isna(value):
            return False
        return bool(value)

    @staticmethod
    def _anomaly_bar_indices(metrics: pd.DataFrame) -> list[int]:
        if COL_CORPORATE_ACTION_ANOMALY not in metrics:
            return []
        return [
            index
            for index, value in enumerate(metrics[COL_CORPORATE_ACTION_ANOMALY])
            if not pd.isna(value) and bool(value)
        ]

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
    def _structural_swing(item, labels, weekly: pd.DataFrame) -> StructuralSwingDTO:
        swing = item.swing
        score = item.evaluation.professional
        structure = score.structure
        smart_money = score.smart_money
        label = labels.get((swing.type, swing.bar_index))
        pivot_week = ProVSAService._week_at(weekly, swing.bar_index)
        confirmation_week = ProVSAService._week_at(weekly, swing.confirmation_index)
        return StructuralSwingDTO(
            bar_index=swing.bar_index,
            confirmation_index=swing.confirmation_index,
            week=pivot_week,
            pivot_bar_index=swing.bar_index,
            pivot_week=pivot_week,
            confirmation_bar_index=swing.confirmation_index,
            confirmation_week=confirmation_week,
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
