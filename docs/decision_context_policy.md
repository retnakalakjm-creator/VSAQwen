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

## API integration boundary

FastAPI analysis builds and returns `decision_context` in the `AnalysisDTO` response and saves the same compact JSON context locally through `DecisionContextStore`.

FastAPI analysis routes latest-symbol scanning through `production_scanner.scan_latest_candidate_production()`. That path bootstraps with a full point-in-time scan when no valid scanner state exists, then resumes from persisted scanner state on later calls. A guarded full-replay fallback remains enabled by default when scanner state is missing, invalid, or incompatible.

FastAPI also exposes a compact decision-context endpoint:

```text
GET /api/symbols/{symbol}/decision-context
```

That endpoint checks the latest completed weekly bar identity. If the saved confirmed `DecisionContext` already matches that latest completed week, the API returns the cached compact context without running scanner analysis. If the context is missing, invalid, developing-mode, or stale, the endpoint refreshes through the production scanner path and saves the new context.

The fast path is intentionally narrower than the full analysis endpoint. It returns only the compact decision context, not full bars, all evidence, structural swings, or chart-ready analysis payloads.

The API uses confirmed weekly bars for this official decision context. Developing/live-bar context remains future work and must be labeled separately when added.

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

This layer is now wired into FastAPI analysis output, local decision-context persistence, the production incremental scanner path, and a cached decision-context endpoint. It is not yet rendered in the React/Next.js frontend and does not yet provide a developing-bar live mode.

## Future integration path

Recommended follow-up PRs:

1. Add a VSA Story panel to the React/Next.js UI.
2. Add click-through linking from story segments to chart events.
3. Add a live validation journal comparing expected next behavior with later bars.
4. Add a market-data provider interface.
5. Add an Upstox read-only provider later, without order placement.
6. Add a developing-bar/live context mode, clearly separated from confirmed signals.
