"""Point-in-time VSA population audit for the current Stopping Volume rule."""
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
from models import Direction
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
    from evidence.engine import EvidenceEngine
    engine = EvidenceEngine()
    engine.collect(
        metrics=replay,
        trend=trend,
        structural_swings=tuple(trend.structure.structural_swings),
        validation_metrics=replay,
    )
    assert engine._ctx is not None
    return replay, engine._ctx


def _outcome(value: float | None) -> str:
    if value is None:
        return "INSUFFICIENT_FORWARD_DATA"
    if value > OUTCOME_THRESHOLD:
        return "POSITIVE_8_BAR"
    if value < -OUTCOME_THRESHOLD:
        return "NEGATIVE_8_BAR"
    return "FLAT_8_BAR"


def inspect_symbol(symbol: str) -> list[dict]:
    metrics = MetricsEngine().calculate(daily_to_weekly(download_data(symbol)))
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

        bar = ctx.current
        prior_close = float(metrics.iloc[index - DECLINE_LOOKBACK][COL_CLOSE])
        pre_close = float(metrics.iloc[index - 1][COL_CLOSE])
        prior_decline = prior_close > pre_close
        bearish_bar = bar.direction == Direction.DOWN
        selling_campaign = bool(has_selling_campaign(ctx))

        current = float(metrics.iloc[index][COL_CLOSE])
        future = float(metrics.iloc[future_index][COL_CLOSE])
        if current != current or future != future or current == 0.0:
            continue

        forward_return = (future - current) / current
        events.append(
            {
                "symbol": symbol,
                "bar_index": index,
                "week": str(metrics.iloc[index][COL_WEEK]),
                "bearish_bar": bearish_bar,
                "prior_decline": prior_decline,
                "selling_campaign": selling_campaign,
                "forward_return": forward_return,
                "8_bar_class": _outcome(forward_return),
            }
        )
    return events


def _summary(events: list[dict]) -> dict:
    positive = sum(e["8_bar_class"] == "POSITIVE_8_BAR" for e in events)
    negative = sum(e["8_bar_class"] == "NEGATIVE_8_BAR" for e in events)
    flat = sum(e["8_bar_class"] == "FLAT_8_BAR" for e in events)
    decisive = positive + negative
    return {
        "events": len(events),
        "positive": positive,
        "negative": negative,
        "flat": flat,
        "decisive": decisive,
        "positive_decisive_rate": positive / decisive if decisive else None,
    }


def main() -> None:
    symbols = tuple(sys.argv[1:]) or DEFAULT_SYMBOLS
    all_events: list[dict] = []
    failures: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(4, len(symbols))) as executor:
        futures = {executor.submit(inspect_symbol, s): s for s in symbols}
        for future, symbol in futures.items():
            try:
                events = future.result()
                all_events.extend(events)
                print({"symbol": symbol, "current_rule_events": len(events)})
            except Exception as exc:
                failures.append({"symbol": symbol, "error": repr(exc)})

    cohorts = {
        "CURRENT_RULE": all_events,
        "CURRENT_RULE_PLUS_BEARISH_BAR": [e for e in all_events if e["bearish_bar"]],
        "CURRENT_RULE_PLUS_BEARISH_BAR_PLUS_PRIOR_DECLINE": [
            e for e in all_events if e["bearish_bar"] and e["prior_decline"]
        ],
        "CURRENT_RULE_PLUS_BEARISH_BAR_PLUS_RECENT_SELLING_PRESSURE": [
            e for e in all_events if e["bearish_bar"] and e["selling_campaign"]
        ],
    }

    print("STOPPING VOLUME VSA POPULATION AUDIT SUMMARY")
    print({
        "symbols_requested": len(symbols),
        "current_rule_events": len(all_events),
        "failures": failures,
        "decline_lookback": DECLINE_LOOKBACK,
        "cohorts": {name: _summary(events) for name, events in cohorts.items()},
    })

    print("STOPPING VOLUME VSA POPULATION AUDIT FLAGS")
    print({
        "bearish_bar_events": sum(e["bearish_bar"] for e in all_events),
        "prior_decline_events": sum(e["prior_decline"] for e in all_events),
        "selling_campaign_events": sum(e["selling_campaign"] for e in all_events),
        "bearish_plus_decline_events": sum(e["bearish_bar"] and e["prior_decline"] for e in all_events),
        "bearish_plus_selling_pressure_events": sum(e["bearish_bar"] and e["selling_campaign"] for e in all_events),
    })


if __name__ == "__main__":
    main()
