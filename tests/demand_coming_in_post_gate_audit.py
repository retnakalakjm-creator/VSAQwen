from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from background.qualification import PatternQualification
from data import daily_to_weekly, download_data
from evidence.demand_coming_in import collect_demand_coming_in
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from model.evidence_result_model import EvidenceResult
from models import EvidenceCode, TrendDirection, TrendState
from professional.scoring_engine import ProfessionalScoringEngine
from scanner import ScannerEngine
from trend import TrendAnalyzer
from tests.decision_outcome_labeling import label_outcome
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS


@dataclass(frozen=True, slots=True)
class BlockedCase:
    symbol: str
    bar_index: int
    direction: str
    state: str
    raw_confidence: float
    gated_confidence: float
    forward_return: float | None
    mfe: float | None
    mae: float | None
    horizon: int


def _has_demand_coming_in(metrics_row, index: int, previous_row) -> bool:
    engine = EvidenceEngine()
    current = engine._create_bar_context(metrics_row, index)
    previous = engine._create_bar_context(previous_row, index - 1)
    return bool(collect_demand_coming_in(SimpleNamespace(current=current, previous=previous)))


def _raw_confidence(engine: ProfessionalScoringEngine, trend, scoring_evidence) -> float:
    result = EvidenceResult(context=scoring_evidence_context(scoring_evidence), evidence=tuple(scoring_evidence))
    trend_score = engine._score_trend(trend)
    supply_score = engine._score_supply(result)
    demand_score = engine._score_demand(result)
    effort_score = engine._score_effort(result)
    strength_score = engine._score_strength(trend_score, demand_score, supply_score, effort_score)
    weakness_score = engine._score_weakness(trend_score, demand_score, supply_score, effort_score)
    from model import ProfessionalScore
    return engine._measure_confidence(
        ProfessionalScore(
            trend=trend_score,
            supply=supply_score,
            demand=demand_score,
            effort=effort_score,
            strength=strength_score,
            weakness=weakness_score,
            confidence=0.0,
        )
    )


def scoring_evidence_context(scoring_evidence):
    if scoring_evidence:
        return SimpleNamespace()
    return SimpleNamespace()


def _direction(candidate) -> int | None:
    if candidate.qualification is PatternQualification.PERSISTENT_BULLISH:
        return 1
    if candidate.qualification is PatternQualification.PERSISTENT_BEARISH:
        return -1
    return None


def collect_blocked_cases(
    symbol: str,
    *,
    sample_bars: int = 520,
    horizons: tuple[int, ...] = (3, 5, 10),
    refresh: bool = False,
) -> list[BlockedCase]:
    daily = download_data(symbol, refresh=refresh)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    scanner = ScannerEngine()
    professional = ProfessionalScoringEngine()
    max_horizon = max(horizons)
    sample_start = max(
        scanner.MIN_REPLAY_BARS + 1,
        len(metrics) - sample_bars - max_horizon,
    )
    history = []
    rows: list[BlockedCase] = []

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics) - max_horizon):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        evidence = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=list(trend.structure.structural_swings),
        )
        history.append(evidence)
        if index < sample_start:
            continue

        candidate = scanner.evaluate(
            trend=trend,
            evidence=evidence,
            history=history,
            bar_index=index,
            week=scanner._week_at(metrics, index),
        )
        direction = _direction(candidate)
        if direction is None:
            continue

        scoring_evidence = candidate.scoring_evidence
        has_event = EvidenceCode.DEMAND_COMING_IN in {
            item.code for item in scoring_evidence
        }
        correcting_bullish = (
            trend.structure.direction is TrendDirection.UP
            and trend.structure.state is TrendState.CORRECTING
        )
        if not has_event or not correcting_bullish:
            continue

        raw_confidence = _raw_confidence(professional, trend, scoring_evidence)
        raw_actionable = candidate.qualification_result.is_actionable_evidence and raw_confidence > 0.0
        if not raw_actionable or candidate.actionable:
            continue

        for horizon in horizons:
            outcome = label_outcome(
                metrics,
                signal_index=index,
                direction=direction,
                horizon=horizon,
            )
            rows.append(
                BlockedCase(
                    symbol=symbol,
                    bar_index=index,
                    direction="bullish",
                    state="correcting",
                    raw_confidence=raw_confidence,
                    gated_confidence=candidate.confidence,
                    forward_return=outcome.forward_return,
                    mfe=outcome.maximum_favorable_excursion,
                    mae=outcome.maximum_adverse_excursion,
                    horizon=horizon,
                )
            )
    return rows


def summarize(rows: list[BlockedCase]) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for horizon in (3, 5, 10):
        bucket = [row for row in rows if row.horizon == horizon]
        returns = [row.forward_return for row in bucket if row.forward_return is not None]
        mfes = [row.mfe for row in bucket if row.mfe is not None]
        maes = [row.mae for row in bucket if row.mae is not None]
        if not returns:
            continue
        result.append(
            {
                "horizon": horizon,
                "cases": len(returns),
                "mean_return": sum(returns) / len(returns),
                "win_rate": sum(value > 0 for value in returns) / len(returns),
                "mean_mfe": sum(mfes) / len(mfes) if mfes else None,
                "mean_mae": sum(maes) / len(maes) if maes else None,
            }
        )
    return result


def run_universe(
    *,
    sample_bars: int = 520,
    refresh: bool = False,
) -> tuple[list[BlockedCase], list[tuple[str, str, str]]]:
    rows: list[BlockedCase] = []
    skipped: list[tuple[str, str, str]] = []
    for symbol in SYMBOLS:
        try:
            rows.extend(collect_blocked_cases(symbol, sample_bars=sample_bars, refresh=refresh))
        except Exception as exc:
            skipped.append((symbol, type(exc).__name__, str(exc)))
    return rows, skipped
