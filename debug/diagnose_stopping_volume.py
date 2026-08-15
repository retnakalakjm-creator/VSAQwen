"""Point-in-time population audit for the current Stopping Volume rule.

Read-only diagnostic. It does not modify production detectors, weights, or
EvidenceEngine registration.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data import daily_to_weekly, download_data
from engine.columns import COL_CLOSE, COL_WEEK
from evidence.campaign import has_selling_campaign
from metrics_engine import MetricsEngine
from smart_money.rules.stopping_volume import StoppingVolumeRule
from trend import TrendAnalyzer

DEFAULT_SYMBOLS = (
    "BHARTIARTL.NS", "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS",
    "INFY.NS", "TCS.NS", "SBIN.NS", "LT.NS",
)
MIN_REPLAY_BARS = 20
FORWARD_HORIZON = 8
OUTCOME_THRESHOLD = 0.02
DECLINE_LOOKBACK = 3


def _audit_context(metrics, index: int):
    replay = metrics.iloc[: index + 1]
    trend = TrendAnalyzer().analyze(replay)
    structural_swings = tuple(trend.structure.structural_swings)

    from evidence.engine import EvidenceEngine

    engine = EvidenceEngine()
    engine.collect(
        metrics=replay,
        trend=trend,
        structural_swings=structural_swings,
        validation_metrics=replay,
    )
    assert engine._ctx is not None
    return replay, engine._ctx


def _outcome(forward_return: float | None) -> str:
    if forward_return is None:
        return "INSUFFICIENT_FORWARD_DATA"
    if forward_return > OUTCOME_THRESHOLD:
        return "POSITIVE_8_BAR"
    if forward_return < -OUTCOME_THRESHOLD:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def inspect_symbol(symbol: str) -> list[dict]:
    daily = download_data(symbol)
    metrics = MetricsEngine().calculate(daily_to_weekly(daily))
    rule = StoppingVolumeRule()
    events: list[dict] = []

    for index in range(max(MIN_REPLAY_BARS, DECLINE_LOOKBACK + 1), len(metrics)):
        future_index = index + FORWARD_HORIZON
        if future_index >= len(metrics):
            break

        replay, ctx = _audit_context(metrics, index)
        audit_ctx = type(
            "StoppingVolumeAuditContext",
            (),
            {
                "metrics": replay,
                "swing": type("Swing", (), {"metrics_index": index})(),
                "history": type("History", (), {"has_previous": index > 0})(),
            },
        )()

        if not rule._detect(audit_ctx):
            continue

        current = float(metrics.iloc[index][COL_CLOSE])
        future = float(metrics.iloc[future_index][COL_CLOSE])
        if current != current or future != future or current == 0.0:
            continue

        prior_close = float(metrics.iloc[index - DECLINE_LOOKBACK][COL_CLOSE])
        last_pre_event_close = float(metrics.iloc[index - 1][COL_CLOSE])
        prior_decline = prior_close > last_pre_event_close
        selling_campaign = bool(has_selling_campaign(ctx))
        forward_return = (future - current) / current

        events.append({
            "symbol": symbol,
            "bar_index": index,
            "week": str(metrics.iloc[index][COL_WEEK]),
            "prior_decline": prior_decline,
            "selling_campaign": selling_campaign,
            "forward_return": forward_return,
            "8_bar_class": _outcome(forward_return),
            "volume_percentile": float(metrics.iloc[index]["volume_percentile"]),
            "spread_percentile": float(metrics.iloc[index]["spread_percentile"]),
            "close_ratio": float(metrics.iloc[index]["close_ratio"]),
        })

    return events


def _summarize(events: list[dict]) -> dict:
    positives = sum(e["8_bar_class"] == "POSITIVE_8_BAR" for e in events)
    negatives = sum(e["8_bar_class"] == "NEGATIVE_8_BAR" for e in events)
    flat = sum(e["8_bar_class"] == "FLAT_8_BAR" for e in events)
    decisive = positives + negatives
    return {
        "events": len(events),
        "positive": positives,
        "negative": negatives,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positives / decisive if decisive else None,
    }


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, symbol): symbol for symbol in symbols}
        for future, symbol in futures.items():
            try:
                events = future.result()
                all_events.extend(events)
                print({"symbol": symbol, "current_rule_events": len(events)})
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})
                print(f"FAILED {symbol}: {exc!r}")

    cohorts = {
        "CURRENT_RULE": all_events,
        "CURRENT_RULE_PLUS_PRIOR_DECLINE": [e for e in all_events if e["prior_decline"]],
        "CURRENT_RULE_PLUS_SELLING_CAMPAIGN": [e for e in all_events if e["selling_campaign"]],
        "CURRENT_RULE_PLUS_BOTH": [
            e for e in all_events if e["prior_decline"] and e["selling_campaign"]
        ],
    }

    print("STOPPING VOLUME POPULATION AUDIT SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "current_rule_events": len(all_events),
        "failures": failures,
        "decline_lookback": DECLINE_LOOKBACK,
        "cohorts": {name: _summarize(events) for name, events in cohorts.items()},
    })

    print("STOPPING VOLUME POPULATION AUDIT FLAGS")
    print({
        "prior_decline_events": sum(e["prior_decline"] for e in all_events),
        "selling_campaign_events": sum(e["selling_campaign"] for e in all_events),
        "both_events": sum(
            e["prior_decline"] and e["selling_campaign"] for e in all_events
        ),
    })

    print("STOPPING VOLUME POPULATION AUDIT EVENTS")
    for event in all_events:
        print(event)


if __name__ == "__main__":
    main()
