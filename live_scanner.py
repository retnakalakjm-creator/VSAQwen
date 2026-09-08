"""Live observation scanner built on the existing production pipeline.

The live loop is stateful: unchanged source data is not re-scanned. This is
an optimization boundary only; the underlying decision engine is unchanged.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from data import completed_weekly_only, daily_to_weekly, download_data
from metrics_engine import MetricsEngine
from production_scanner import scan_actionable_production
from scanner import ScannerEngine

DEFAULT_SYMBOLS = ("SRF.NS",)
DEFAULT_INTERVAL_SECONDS = 900
DEFAULT_MAX_WORKERS = 4


@dataclass(slots=True)
class _LiveSymbolState:
    """Cached live state for one symbol within a scanner process."""

    latest_daily_key: Any = None
    observation: dict[str, Any] | None = None


def _candidate_payload(symbol: str, candidate: Any) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "bar_index": candidate.bar_index,
        "week": candidate.week,
        "signal_bar_index": candidate.signal_bar_index,
        "signal_week": candidate.signal_week,
        "signal_bar_anomaly": bool(getattr(candidate, "signal_bar_anomaly", False)),
        "signal_bar_anomaly_reason": getattr(candidate, "signal_bar_anomaly_reason", None),
        "execution_bar_index": candidate.execution_bar_index,
        "execution_week": candidate.execution_week,
        "execution_available": candidate.execution_available,
        "execution_pending": candidate.execution_pending,
        "execution_note": candidate.execution_note,
        "qualification": str(candidate.qualification),
        "actionable": bool(candidate.actionable),
        "reason": candidate.reason,
        "net_strength": candidate.net_strength,
        "net_pressure": candidate.net_pressure,
        "confidence": candidate.confidence,
        "target_bar_evidence_codes": list(candidate.target_bar_evidence_codes),
        "campaign_evidence_codes": list(candidate.campaign_evidence_codes),
        "qualifying_evidence_codes": list(candidate.qualifying_evidence_codes),
        "scoring_evidence_codes": list(candidate.scoring_evidence_codes),
        "scoring_bar_index": candidate.scoring_bar_index,
        "scoring_evidence_age": candidate.scoring_evidence_age,
        "used_fallback_evidence": candidate.used_fallback_evidence,
    }


def _error_payload(symbol: str, exc: Exception) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "bar_index": None,
        "week": None,
        "signal_bar_index": None,
        "signal_week": None,
        "signal_bar_anomaly": False,
        "signal_bar_anomaly_reason": None,
        "execution_bar_index": None,
        "execution_week": None,
        "execution_available": False,
        "execution_pending": False,
        "execution_note": "Symbol scan failed before a candidate could be evaluated.",
        "qualification": "ERROR",
        "actionable": False,
        "reason": str(exc),
        "net_strength": 0.0,
        "net_pressure": 0.0,
        "confidence": 0.0,
        "target_bar_evidence_codes": [],
        "campaign_evidence_codes": [],
        "qualifying_evidence_codes": [],
        "scoring_evidence_codes": [],
        "scoring_bar_index": None,
        "scoring_evidence_age": None,
        "used_fallback_evidence": False,
        "error": type(exc).__name__,
    }


def _latest_daily_key(daily: Any) -> Any:
    if daily.empty:
        return None
    return daily.index[-1]


def _scan_from_daily(
    symbol: str,
    daily: Any,
    *,
    use_incremental: bool = True,
) -> dict[str, Any]:
    weekly = completed_weekly_only(daily_to_weekly(daily))
    metrics = MetricsEngine().calculate(weekly)
    if use_incremental:
        candidates = scan_actionable_production(metrics, symbol=symbol)
    else:
        candidates = ScannerEngine().scan_actionable(metrics)

    if candidates:
        return _candidate_payload(symbol, candidates[0])

    latest_index = len(metrics) - 1
    latest_week = None
    if latest_index >= 0:
        value = metrics.iloc[latest_index].get("week_beginning")
        if value is not None:
            latest_week = str(value)

    return {
        "symbol": symbol,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "bar_index": latest_index if latest_index >= 0 else None,
        "week": latest_week,
        "signal_bar_index": latest_index if latest_index >= 0 else None,
        "signal_week": latest_week,
        "signal_bar_anomaly": False,
        "signal_bar_anomaly_reason": None,
        "execution_bar_index": None,
        "execution_week": None,
        "execution_available": False,
        "execution_pending": False,
        "execution_note": "No actionable setup is present on the latest completed weekly bar.",
        "qualification": "UNQUALIFIED",
        "actionable": False,
        "reason": "No actionable candidate on the latest completed weekly bar.",
        "net_strength": 0.0,
        "net_pressure": 0.0,
        "confidence": 0.0,
        "target_bar_evidence_codes": [],
        "campaign_evidence_codes": [],
        "qualifying_evidence_codes": [],
        "scoring_evidence_codes": [],
        "scoring_bar_index": None,
        "scoring_evidence_age": None,
        "used_fallback_evidence": False,
    }


def _worker_count(symbols: tuple[str, ...], max_workers: int) -> int:
    if max_workers <= 0:
        raise ValueError("max_workers must be greater than zero")
    return min(max_workers, max(1, len(symbols)))


def scan_symbol(symbol: str, *, use_incremental: bool = True) -> dict[str, Any]:
    """Evaluate one symbol through the existing production scanner path."""
    daily = download_data(symbol, refresh=False)
    return _scan_from_daily(symbol, daily, use_incremental=use_incremental)


def _scan_symbol_safe(symbol: str, *, use_incremental: bool = True) -> dict[str, Any]:
    try:
        return scan_symbol(symbol, use_incremental=use_incremental)
    except Exception as exc:
        return _error_payload(symbol, exc)


def scan_symbols_parallel(
    symbols: tuple[str, ...],
    *,
    use_incremental: bool = True,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> list[dict[str, Any]]:
    """Scan many symbols concurrently while preserving input order.

    Each symbol is isolated: a failure for one symbol returns an error payload
    and does not prevent other symbols from being evaluated.
    """
    if not symbols:
        return []

    workers = _worker_count(symbols, max_workers)
    if workers == 1:
        return [
            _scan_symbol_safe(symbol, use_incremental=use_incremental)
            for symbol in symbols
        ]

    with ThreadPoolExecutor(max_workers=workers) as executor:
        return list(
            executor.map(
                lambda symbol: _scan_symbol_safe(
                    symbol,
                    use_incremental=use_incremental,
                ),
                symbols,
            )
        )


def _observation_signature(observation: dict[str, Any]) -> tuple[Any, ...]:
    return (
        observation["week"],
        observation["signal_bar_index"],
        observation.get("signal_bar_anomaly", False),
        observation["execution_bar_index"],
        observation["actionable"],
        observation["qualification"],
        observation["net_strength"],
        observation["net_pressure"],
        tuple(observation["target_bar_evidence_codes"]),
        tuple(observation["scoring_evidence_codes"]),
    )


def _print_observation(observation: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(observation, sort_keys=True))
        return

    print("=" * 72)
    print(f"Symbol         : {observation['symbol']}")
    print(f"Evaluated (UTC): {observation['evaluated_at']}")
    print(f"Signal week    : {observation['signal_week']}")
    print(f"Signal anomaly : {observation['signal_bar_anomaly']}")
    print(f"Execution week : {observation['execution_week']}")
    print(f"Execution note : {observation['execution_note']}")
    print(f"Qualification  : {observation['qualification']}")
    print(f"Actionable     : {observation['actionable']}")
    print(f"Net strength   : {observation['net_strength']:.4f}")
    print(f"Net pressure   : {observation['net_pressure']:.4f}")
    print(f"Confidence     : {observation['confidence']:.4f}")
    print(f"Target evidence: {observation['target_bar_evidence_codes']}")
    print(f"Scoring evidence: {observation['scoring_evidence_codes']}")
    print(f"Evidence age   : {observation['scoring_evidence_age']}")
    print(f"Fallback       : {observation['used_fallback_evidence']}")
    print(f"Reason         : {observation['reason']}")


def run_once(
    symbols: tuple[str, ...],
    as_json: bool,
    *,
    use_incremental: bool = True,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> list[dict[str, Any]]:
    observations = scan_symbols_parallel(
        symbols,
        use_incremental=use_incremental,
        max_workers=max_workers,
    )
    for observation in observations:
        _print_observation(observation, as_json)
    return observations


def _live_observation_for_symbol(
    symbol: str,
    state: _LiveSymbolState,
    *,
    use_incremental: bool = True,
) -> dict[str, Any] | None:
    try:
        daily = download_data(symbol, refresh=False)
        daily_key = _latest_daily_key(daily)

        if state.observation is not None and state.latest_daily_key == daily_key:
            return None

        observation = _scan_from_daily(
            symbol,
            daily,
            use_incremental=use_incremental,
        )
        state.latest_daily_key = daily_key
        state.observation = observation
        return observation
    except Exception as exc:
        observation = _error_payload(symbol, exc)
        state.observation = observation
        return observation


def run_live(
    symbols: tuple[str, ...],
    interval_seconds: int,
    as_json: bool,
    *,
    use_incremental: bool = True,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> None:
    """Poll source data and rescan only when a new source bar appears."""
    states = {symbol: _LiveSymbolState() for symbol in symbols}
    workers = _worker_count(symbols, max_workers)

    while True:
        if workers == 1:
            observations = [
                _live_observation_for_symbol(
                    symbol,
                    states[symbol],
                    use_incremental=use_incremental,
                )
                for symbol in symbols
            ]
        else:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                observations = list(
                    executor.map(
                        lambda symbol: _live_observation_for_symbol(
                            symbol,
                            states[symbol],
                            use_incremental=use_incremental,
                        ),
                        symbols,
                    )
                )

        for observation in observations:
            if observation is not None:
                _print_observation(observation, as_json)

        time.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="ProVSA Live Observation Scanner")
    parser.add_argument("symbols", nargs="*", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--once", action="store_true", help="Run one observation cycle and exit")
    parser.add_argument("--json", action="store_true", help="Print observations as JSON")
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help="Maximum parallel symbol scans. Use 1 for sequential scanning.",
    )
    parser.add_argument(
        "--full-replay",
        action="store_true",
        help="Use the original full replay scanner instead of the incremental production path.",
    )
    args = parser.parse_args()

    if not args.symbols:
        raise ValueError("At least one symbol is required")
    if args.interval <= 0:
        raise ValueError("interval must be greater than zero")
    if args.workers <= 0:
        raise ValueError("workers must be greater than zero")

    symbols = tuple(dict.fromkeys(args.symbols))
    use_incremental = not args.full_replay
    if args.once:
        run_once(
            symbols,
            args.json,
            use_incremental=use_incremental,
            max_workers=args.workers,
        )
    else:
        run_live(
            symbols,
            args.interval,
            args.json,
            use_incremental=use_incremental,
            max_workers=args.workers,
        )


if __name__ == "__main__":
    main()
