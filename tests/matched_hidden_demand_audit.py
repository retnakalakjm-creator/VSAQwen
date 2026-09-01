from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE_POSITION, COL_DIRECTION, COL_VOLUME_CLASS
from metrics_engine import MetricsEngine
from models import ClosePosition, Direction, VolumeClass
from trend import TrendAnalyzer
from tests.run_nse_increasing_demand_universe_audit import SYMBOLS
from tests.decision_outcome_labeling import label_outcome


@dataclass(frozen=True, slots=True)
class AuditCase:
    symbol: str
    bar_index: int
    trend_direction: str
    trend_state: str
    horizon: int
    forward_return: float | None
    mfe: float | None
    mae: float | None


@dataclass(frozen=True, slots=True)
class MatchedPair:
    target: AuditCase
    control: AuditCase


def is_hidden_demand(bar) -> bool:
    return (
        Direction(int(bar[COL_DIRECTION])) == Direction.DOWN
        and VolumeClass(int(bar[COL_VOLUME_CLASS])) >= VolumeClass.HIGH
        and ClosePosition(int(bar[COL_CLOSE_POSITION])) >= ClosePosition.UPPER
    )


def _case_context(metrics, index: int) -> tuple[str, str]:
    trend = TrendAnalyzer().analyze(metrics.iloc[: index + 1].copy())
    return trend.structure.direction.value, trend.structure.state.value


def scan_cases(
    symbol: str,
    sample_bars: int = 520,
    horizons: tuple[int, ...] = (3, 5, 10),
    refresh: bool = False,
) -> list[tuple[AuditCase, bool]]:
    daily = download_data(symbol, refresh=refresh)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    sample_start = max(20, len(metrics) - sample_bars - max(horizons))
    cases: list[tuple[AuditCase, bool]] = []

    for index in range(sample_start, len(metrics)):
        trend_direction, trend_state = _case_context(metrics, index)
        is_target = is_hidden_demand(metrics.iloc[index])
        for horizon in horizons:
            if index + horizon >= len(metrics):
                continue
            outcome = label_outcome(
                metrics,
                signal_index=index,
                direction=1,
                horizon=horizon,
            )
            cases.append((
                AuditCase(
                    symbol=symbol,
                    bar_index=index,
                    trend_direction=trend_direction,
                    trend_state=trend_state,
                    horizon=horizon,
                    forward_return=outcome.forward_return,
                    mfe=outcome.maximum_favorable_excursion,
                    mae=outcome.maximum_adverse_excursion,
                ),
                is_target,
            ))
    return cases


def _nearest_control(
    target: AuditCase,
    controls: list[AuditCase],
    used: set[tuple[str, int, int]],
) -> AuditCase | None:
    candidates = [
        control
        for control in controls
        if control.symbol == target.symbol
        and control.horizon == target.horizon
        and control.trend_direction == target.trend_direction
        and control.trend_state == target.trend_state
        and control.bar_index != target.bar_index
        and (control.symbol, control.bar_index, control.horizon) not in used
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda item: abs(item.bar_index - target.bar_index))


def build_matches(all_cases: list[tuple[AuditCase, bool]]) -> list[MatchedPair]:
    targets = [case for case, target in all_cases if target]
    controls = [case for case, target in all_cases if not target]
    used: set[tuple[str, int, int]] = set()
    pairs: list[MatchedPair] = []
    for target in sorted(targets, key=lambda item: (item.symbol, item.horizon, item.bar_index)):
        control = _nearest_control(target, controls, used)
        if control is None:
            continue
        used.add((control.symbol, control.bar_index, control.horizon))
        pairs.append(MatchedPair(target=target, control=control))
    return pairs


def summarize(pairs: list[MatchedPair]) -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    for horizon in (3, 5, 10):
        bucket = [pair for pair in pairs if pair.target.horizon == horizon]
        returns = [
            (pair.target.forward_return, pair.control.forward_return)
            for pair in bucket
            if pair.target.forward_return is not None
            and pair.control.forward_return is not None
        ]
        if not returns:
            continue
        target_mean = sum(item[0] for item in returns) / len(returns)
        control_mean = sum(item[1] for item in returns) / len(returns)
        rows.append({
            "horizon": horizon,
            "pairs": len(returns),
            "target_mean_return": target_mean,
            "control_mean_return": control_mean,
            "return_delta": target_mean - control_mean,
        })
    return rows


__all__ = ["AuditCase", "MatchedPair", "build_matches", "is_hidden_demand", "scan_cases", "summarize"]
