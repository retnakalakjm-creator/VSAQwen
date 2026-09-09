# Analysis-only trade planning layer

PR #67 introduces a dedicated trade-planning layer after the frontend readability work and weekly Bar-by-Bar professional interpretation.

The layer is intentionally **decision support only**. It turns the confirmed weekly VSA context and recent structure into a readable planning draft. It does not place, modify, cancel, simulate, or route orders.

## API

```text
GET /api/symbols/{symbol}/trade-plan
```

The endpoint returns a single planning draft for the latest completed weekly analysis.

## Response shape

```json
{
  "symbol": "SRF.NS",
  "timeframe": "1W",
  "latest_week": "2026-08-31 00:00:00",
  "plan": {
    "posture": "Wait for pullback",
    "setup_type": "Bullish pullback watch",
    "reference_price": 100.0,
    "support": {
      "label": "Support area from HL",
      "price": 96.0,
      "lower": 95.04,
      "upper": 96.96,
      "source": "Confirmed swing low at 2026-08-31 00:00:00",
      "note": "Use as planning context; confirmation still comes from VSA behavior around the area."
    },
    "resistance": {
      "label": "Resistance area from HH",
      "price": 112.0,
      "lower": 110.88,
      "upper": 113.12,
      "source": "Confirmed swing high at 2026-08-31 00:00:00",
      "note": "Use as planning context; it is not a guaranteed target."
    },
    "entry_condition": "Review only if price pulls back toward support and the pullback shows No Supply, fresh demand, or a strong recovery close.",
    "confirmation_trigger": "Fresh demand or No Supply after pullback confirms the plan.",
    "invalidation_condition": "A decisive breakdown below support invalidates the plan.",
    "risk_reading": "Risk is moderate; wait for a controlled pullback or stronger confirmation.",
    "reward_reading": "Reward potential is moderate and depends on clean follow-through.",
    "notes": [
      "Decision-support plan only; this is not an order signal.",
      "No broker, account, funds, holdings, margin, position-size, or order action is produced.",
      "Use completed weekly context only; review lower-timeframe execution separately if needed."
    ],
    "analysis_only": true
  }
}
```

## Inputs

The planner consumes the existing confirmed weekly analysis result:

- latest completed weekly close
- confirmed decision context
- supply/demand bias
- tradability/decision labels
- VSA confirmation and invalidation text
- latest valid structural swing low as support context
- latest valid structural swing high as resistance context

It does **not** download data directly, run provider calls, replay scanner loops, or persist planner artifacts.

## Boundaries

Allowed:

- setup posture such as `Wait for pullback`, `Wait for confirmation`, or `Review setup`
- setup type such as `Bullish pullback watch`
- support/resistance planning context from confirmed structural swings
- entry condition wording that requires VSA confirmation
- invalidation wording
- risk/reward readability text

Forbidden in this layer:

- broker integration
- order placement, modification, cancellation, or routing
- account, funds, holdings, margin, or position API access
- credential/token persistence
- position sizing
- automatic execution
- overwriting scanner scores, ranks, or historical audit data

## Runtime behavior

The API endpoint calls the existing confirmed `analyze_symbol(...)` path once and builds the plan from the returned analysis payload. The planner itself then performs only a bounded scan over the already-returned bars and structural swings.

This keeps the layer consistent with the confirmed production path while avoiding additional provider downloads or replay loops inside `trade_planner.py`.

## Future frontend wiring

A later frontend PR can render the returned plan in a dedicated Trade Plan tab or Dashboard card. That UI should preserve the analysis-only wording and should not add broker/order/account controls.
