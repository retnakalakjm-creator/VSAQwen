from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from background.qualification import PatternQualification
from data import daily_to_weekly, download_data
from evidence.demand_coming_in import collect_demand_coming_in
from evidence.engine import EvidenceEngine
from metrics_engine import MetricsEngine
from scanner import ScannerEngine
from tests.decision_outcome_labeling import label_outcome
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS
from trend import TrendAnalyzer


@dataclass(frozen=True, slots=True)
class AuditCase:
    symbol: str
    bar_index: int
    direction: str
    state: str
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


def _has_event(metrics_row, index: int, previous_row) -> bool:
    factory = EvidenceEngine()
    current = factory._create_bar_context(metrics_row, index)
    previous = factory._create_bar_context(previous_row, index - 1)
    return bool(collect_demand_coming_in(SimpleNamespace(current=current, previous=previous)))


def _scan_cases(symbol: str, sample_bars: int, horizons: tuple[int, ...], refresh: bool = False) -> list[tuple[AuditCase, bool]]:
    daily = download_data(symbol, refresh=refresh)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
    scanner = ScannerEngine()
    sample_start = max(scanner.MIN_REPLAY_BARS + 1, len(metrics) - sample_bars - max(horizons))
    cases: list[tuple[AuditCase, bool]] = []
    history = []

    for index in range(scanner.MIN_REPLAY_BARS, len(metrics)):
        replay = metrics.iloc[: index + 1].copy()
        trend = TrendAnalyzer().analyze(replay)
        evidence = EvidenceEngine().collect(
            metrics=replay,
            trend=trend,
            structural_swings=list(trend.structure.structural_swings),
        )
        history.append(evidence)
        if index < sample_start or index + min(horizons) >= len(metrics):
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

        has_event = _has_event(metrics.iloc[index], index, metrics.iloc[index - 1])
        for horizon in horizons:
            if index + horizon >= len(metrics):
                continue
            outcome = label_outcome(metrics, signal_index=index, direction=direction, horizon=horizon)
            cases.append((AuditCase(
                symbol=symbol,
                bar_index=index,
                direction=_direction_name(direction),
                state=str(trend.structure.state.value),
                horizon=horizon,
                score=candidate.base_score,
                pressure=candidate.net_pressure,
                vsa_age=candidate.scoring_evidence_age,
                forward_return=outcome.forward_return,
                mfe=outcome.maximum_favorable_excursion,
                mae=outcome.maximum_adverse_excursion,
            ), has_event))
    return cases


def _nearest_control(target: AuditCase, controls: list[AuditCase], *, score_band: float, pressure_band: float, max_age_gap: int, used: set[tuple[str, int, int]]) -> AuditCase | None:
    candidates = [
        c for c in controls
        if c.symbol == target.symbol
        and c.direction == target.direction
        and c.state == target.state
        and c.horizon == target.horizon
        and abs(c.score - target.score) <= score_band
        and abs(c.pressure - target.pressure) <= pressure_band
        and abs((c.vsa_age or 0) - (target.vsa_age or 0)) <= max_age_gap
        and c.bar_index != target.bar_index
        and (c.symbol, c.bar_index, c.horizon) not in used
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda c: (
        abs(c.score - target.score),
        abs(c.pressure - target.pressure),
        abs((c.vsa_age or 0) - (target.vsa_age or 0)),
        abs(c.bar_index - target.bar_index),
    ))


def build_matches(all_cases: list[tuple[AuditCase, bool]], *, score_band: float = 0.10, pressure_band: float = 0.25, max_age_gap: int = 1) -> list[MatchedPair]:
    targets = [case for case, has_event in all_cases if has_event]
    controls = [case for case, has_event in all_cases if not has_event]
    pairs: list[MatchedPair] = []
    used: set[tuple[str, int, int]] = set()
    for target in sorted(targets, key=lambda c: (c.horizon, c.symbol, c.bar_index)):
        control = _nearest_control(target, controls, score_band=score_band, pressure_band=pressure_band, max_age_gap=max_age_gap, used=used)
        if control is None:
            continue
        used.add((control.symbol, control.bar_index, control.horizon))
        pairs.append(MatchedPair(
            target=target,
            control=control,
            score_gap=abs(target.score - control.score),
            pressure_gap=abs(target.pressure - control.pressure),
            age_gap=abs((target.vsa_age or 0) - (control.vsa_age or 0)),
        ))
    return pairs


def summarize(pairs: list[MatchedPair]) -> list[dict[str, float | int | str | None]]:
    rows: list[dict[str, float | int | str | None]] = []
    for horizon in (3, 5, 10):
        bucket = [p for p in pairs if p.target.horizon == horizon]
        if not bucket:
            continue
        target = [p.target.forward_return for p in bucket if p.target.forward_return is not None]
        control = [p.control.forward_return for p in bucket if p.control.forward_return is not None]
        target_mean = sum(target) / len(target) if target else None
        control_mean = sum(control) / len(control) if control else None
        rows.append({
            "horizon": horizon,
            "pairs": len(bucket),
            "target_mean_return": target_mean,
            "control_mean_return": control_mean,
            "return_delta": None if target_mean is None or control_mean is None else target_mean - control_mean,
        })
    return rows
