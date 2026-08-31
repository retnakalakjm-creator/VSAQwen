from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from background.qualification import PatternQualification
from data import daily_to_weekly, download_data
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from scanner import ScannerEngine
from tests.decision_outcome_audit import CONFIRMATION_ONLY_CODES, mask_confirmation_only
from tests.decision_outcome_labeling import label_outcome
from trend import TrendAnalyzer


@dataclass(frozen=True, slots=True)
class AuditCase:
    symbol: str
    bar_index: int
    direction: str
    state: str
    change: str
    horizon: int
    score: float
    pressure: float
    vsa_age: int | None
    forward_return: float | None
    mfe: float | None
    mae: float | None


@dataclass(frozen=True, slots=True)
class MatchedPair:
    target: AuditCase
    control: AuditCase
    horizon: int
    score_gap: float
    pressure_gap: float
    age_gap: int


def _direction(candidate) -> int | None:
    if candidate.qualification is PatternQualification.PERSISTENT_BULLISH:
        return 1
    if candidate.qualification is PatternQualification.PERSISTENT_BEARISH:
        return -1
    return None


def _direction_name(direction: int | None) -> str:
    return "bullish" if direction == 1 else "bearish" if direction == -1 else "unknown"


def _has_increasing_demand(evidence) -> bool:
    return any(str(item.code.value) == "increasing_demand" for item in evidence.evidence if item.code in CONFIRMATION_ONLY_CODES)


def _scan_cases(symbol: str, sample_bars: int, horizons: tuple[int, ...], refresh: bool = False) -> list[tuple[AuditCase, bool]]:
    daily = download_data(symbol, refresh=refresh)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    scanner = ScannerEngine()
    sample_start = max(scanner.MIN_REPLAY_BARS, len(metrics) - sample_bars - max(horizons))
    history = []
    cases: list[tuple[AuditCase, bool]] = []

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        evidence = EvidenceEngine().collect(metrics=replay, trend=trend, structural_swings=list(trend.structure.structural_swings))
        history.append(evidence)
        if index < sample_start or index + min(horizons) >= len(metrics) or not _has_increasing_demand(evidence):
            continue

        baseline = scanner.evaluate(trend=trend, evidence=evidence, history=history, bar_index=index, week=scanner._week_at(metrics, index))
        masked = scanner.evaluate(trend=trend, evidence=mask_confirmation_only(evidence), history=history, bar_index=index, week=scanner._week_at(metrics, index))
        direction = _direction(baseline)
        if direction is None:
            continue

        changed = baseline.actionable != masked.actionable
        for horizon in horizons:
            if index + horizon >= len(metrics):
                continue
            outcome = label_outcome(metrics, signal_index=index, direction=direction, horizon=horizon)
            cases.append((AuditCase(
                symbol=symbol,
                bar_index=index,
                direction=_direction_name(direction),
                state=str(trend.structure.state.value),
                change=f"{baseline.actionable}->{masked.actionable}",
                horizon=horizon,
                score=baseline.base_score,
                pressure=baseline.net_pressure,
                vsa_age=baseline.scoring_evidence_age,
                forward_return=outcome.forward_return,
                mfe=outcome.maximum_favorable_excursion,
                mae=outcome.maximum_adverse_excursion,
            ), changed))
    return cases


def _nearest_control(target: AuditCase, controls: list[AuditCase], *, score_band: float, pressure_band: float, max_age_gap: int, used: set[tuple[str, int, int]]) -> AuditCase | None:
    candidates = [c for c in controls
                  if c.symbol == target.symbol
                  and c.direction == target.direction
                  and c.state == target.state
                  and c.horizon == target.horizon
                  and abs(c.score - target.score) <= score_band
                  and abs(c.pressure - target.pressure) <= pressure_band
                  and abs((c.vsa_age or 0) - (target.vsa_age or 0)) <= max_age_gap
                  and c.bar_index != target.bar_index
                  and (c.symbol, c.bar_index, c.horizon) not in used]
    if not candidates:
        return None
    return min(candidates, key=lambda c: (abs(c.score-target.score), abs(c.pressure-target.pressure), abs((c.vsa_age or 0)-(target.vsa_age or 0)), abs(c.bar_index-target.bar_index)))


def build_matches(all_cases: list[tuple[AuditCase, bool]], *, score_band: float = 0.10, pressure_band: float = 0.25, max_age_gap: int = 1) -> list[MatchedPair]:
    targets = [case for case, changed in all_cases if changed]
    controls = [case for case, changed in all_cases if not changed]
    pairs: list[MatchedPair] = []
    used: set[tuple[str, int, int]] = set()
    for target in sorted(targets, key=lambda c: (c.horizon, c.symbol, c.bar_index)):
        control = _nearest_control(target, controls, score_band=score_band, pressure_band=pressure_band, max_age_gap=max_age_gap, used=used)
        if control is None:
            continue
        used.add((control.symbol, control.bar_index, control.horizon))
        pairs.append(MatchedPair(target=target, control=control, horizon=target.horizon, score_gap=abs(target.score-control.score), pressure_gap=abs(target.pressure-control.pressure), age_gap=abs((target.vsa_age or 0)-(control.vsa_age or 0))))
    return pairs


def summarize(pairs: list[MatchedPair]) -> dict[str, float | int | None]:
    if not pairs:
        return {"pairs": 0, "target_mean_return": None, "control_mean_return": None, "return_delta": None}
    target_returns = [p.target.forward_return for p in pairs if p.target.forward_return is not None]
    control_returns = [p.control.forward_return for p in pairs if p.control.forward_return is not None]
    target_mean = sum(target_returns)/len(target_returns) if target_returns else None
    control_mean = sum(control_returns)/len(control_returns) if control_returns else None
    return {"pairs": len(pairs), "target_mean_return": target_mean, "control_mean_return": control_mean, "return_delta": None if target_mean is None or control_mean is None else target_mean-control_mean}
