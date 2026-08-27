"""Live observation scanner built on the existing production pipeline.

V1 deliberately stops at decision output. It does not connect to a broker,
place orders, or alter production evidence/scoring policy.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from typing import Any

from data import daily_to_weekly, download_data
from metrics_engine import MetricsEngine
from scanner import ScannerEngine

DEFAULT_SYMBOLS = ("SRF.NS",)
DEFAULT_INTERVAL_SECONDS = 900


def _candidate_payload(symbol: str, candidate: Any) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "bar_index": candidate.bar_index,
        "week": candidate.week,
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


def scan_symbol(symbol: str) -> dict[str, Any]:
    """Evaluate one symbol through the existing production scanner path."""
    daily = download_data(symbol, refresh=True)
    weekly = daily_to_weekly(daily)
    metrics = MetricsEngine().calculate(weekly)
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
        "qualification": "UNQUALIFIED",
        "actionable": False,
        "reason": "No actionable candidate on the latest available weekly bar.",
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


def _observation_signature(observation: dict[str, Any]) -> tuple[Any, ...]:
    """Identify a changed latest observation without using wall-clock time."""
    return (
        observation["week"],
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
    print(f"Week           : {observation['week']}")
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


def run_once(symbols: tuple[str, ...], as_json: bool) -> list[dict[str, Any]]:
    observations = []
    for symbol in symbols:
        observation = scan_symbol(symbol)
        observations.append(observation)
        _print_observation(observation, as_json)
    return observations


def run_live(symbols: tuple[str, ...], interval_seconds: int, as_json: bool) -> None:
    """Poll refreshed market data and report changed observations."""
    previous: dict[str, tuple[Any, ...]] = {}
    while True:
        for symbol in symbols:
            observation = scan_symbol(symbol)
            signature = _observation_signature(observation)
            if previous.get(symbol) != signature:
                _print_observation(observation, as_json)
                previous[symbol] = signature
        time.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="ProVSA Live Observation Scanner")
    parser.add_argument("symbols", nargs="*", default=list(DEFAULT_SYMBOLS))
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SECONDS)
    parser.add_argument("--once", action="store_true", help="Run one observation cycle and exit")
    parser.add_argument("--json", action="store_true", help="Print observations as JSON")
    args = parser.parse_args()

    if not args.symbols:
        raise ValueError("At least one symbol is required")
    if args.interval <= 0:
        raise ValueError("interval must be greater than zero")

    symbols = tuple(dict.fromkeys(args.symbols))
    if args.once:
        run_once(symbols, args.json)
    else:
        run_live(symbols, args.interval, args.json)


if __name__ == "__main__":
    main()
