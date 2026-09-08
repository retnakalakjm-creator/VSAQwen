# Compact VSA Decision Context Policy

## Purpose

The decision context layer stores a compact, local, human-readable market interpretation for one symbol and timeframe.

It exists to support the local ProVSA Command Centre UI:

```text
latest scanner read
recent VSA evidence
recent structural swings
tradability status
VSA story summary
what to expect next
confirmation / invalidation conditions
```

This is not a full historical event database and not an automated trading system.

## What is persisted

The default context keeps only:

```text
last 12 decision-relevant VSA/evidence events
last 8 structural swings
latest qualification/actionability result
latest supply/demand bias
latest phase estimate
latest tradability label
story/summary fields
confirmation and invalidation notes
```

The defaults are intentionally small so the local UI can reopen quickly and explain the current situation without replaying or storing the whole market history.

## What is not persisted

The context store must not persist:

```text
full historical event logs
full audit datasets
all historical scanner candidates
tick-by-tick market data
broker credentials
orders
positions
trade execution requests
```

Historical research remains the responsibility of the Milestone 3 audit/reporting modules.

## Decision-support only

The decision context is analysis-only. It may say:

```text
tradable_now
wait_for_pullback
wait_for_confirmation
observation_only
avoid
```

These labels are for human review only. They must never place orders, modify orders, size positions, or trigger automatic trading.

## Confirmed vs developing modes

Confirmed mode should use only completed weekly bars and may support the official scanner decision.

Developing mode may use incomplete/live data in the future, but it must be labeled as developing context only. Developing observations can warn the user that demand/supply may be forming, but they must not be treated as confirmed VSA signals.

## Current implementation boundary

`decision_context.py` adds:

```text
DecisionContext
DecisionContextEvent
StructuralSwingMemory
VSAStorySummary
DecisionContextStore
build_decision_context
```

The builder accepts the latest scanner candidate and intentionally keeps only recent decision-relevant events/swings.

FastAPI analysis responses now include a `decision_context` object and save the same compact JSON context locally through `DecisionContextStore`.

This API integration still uses the existing point-in-time scanner path. It does not yet switch FastAPI to the production incremental scanner path, add WebSockets, add developing-bar live mode, or render the story in the React/Next.js frontend.

## Future integration path

Recommended follow-up PRs:

1. Make FastAPI use the production incremental scanner path and return saved `DecisionContext` when no new completed bar exists.
2. Add a VSA Story panel to the React/Next.js UI.
3. Add click-through linking from story segments to chart events.
4. Add a live validation journal comparing expected next behavior with later bars.
5. Add a market-data provider interface.
6. Add an Upstox read-only provider later, without order placement.