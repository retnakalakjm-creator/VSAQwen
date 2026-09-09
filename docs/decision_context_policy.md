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

Developing mode may use incomplete/live data, but it must be labeled as developing context only. Developing observations can warn the user that demand/supply may be forming, but they must not be treated as confirmed VSA signals.

Developing context is preview-only. It must not overwrite confirmed `DecisionContext` files, update scanner state snapshots, create decision-journal entries, or change official qualification/actionability decisions.

## API integration boundary

FastAPI analysis builds and returns `decision_context` in the `AnalysisDTO` response and saves the same compact JSON context locally through `DecisionContextStore`.

FastAPI analysis routes latest-symbol scanning through `production_scanner.scan_latest_candidate_production()`. That path bootstraps with a full point-in-time scan when no valid scanner state exists, then resumes from persisted scanner state on later calls. A guarded full-replay fallback remains enabled by default when scanner state is missing, invalid, or incompatible.

FastAPI also exposes a compact confirmed decision-context endpoint:

```text
GET /api/symbols/{symbol}/decision-context
```

That endpoint checks the latest completed weekly bar identity. If the saved confirmed `DecisionContext` already matches that latest completed week, the API returns the cached compact context without running scanner analysis. If the context is missing, invalid, developing-mode, or stale, the endpoint refreshes through the production scanner path and saves the new confirmed context.

Freshly rebuilt confirmed contexts also upsert a compact `DecisionJournalEntry` through `DecisionJournalStore`. Cached decision-context responses do not create duplicate journal entries because no new analysis was performed.

FastAPI exposes a separate developing decision-context endpoint:

```text
GET /api/symbols/{symbol}/decision-context/developing
```

That endpoint uses the latest available weekly data, including a potentially incomplete current week, and returns a `DecisionContext` with `mode=developing`. It is an early-warning preview only. It uses the point-in-time scanner without scanner-state persistence and does not save decision-context JSON or upsert decision-journal entries.

The API also exposes journal endpoints:

```text
GET /api/symbols/{symbol}/decision-journal
GET /api/symbols/{symbol}/decision-journal/evaluations
```

The journal list endpoint returns saved compact expectation snapshots. The evaluation endpoint compares those snapshots with completed weekly bars. Evaluation is read-only by default and only updates saved journal statuses when `persist_status=true` is explicitly passed.

Journal evaluation payloads include source context week/bar metadata so UI clients can link a validation outcome back to the original story source bar without parsing opaque entry IDs.

The fast path is intentionally narrower than the full analysis endpoint. It returns only the compact decision context, not full bars, all evidence, structural swings, or chart-ready analysis payloads.

Confirmed API paths use completed weekly bars for official decision context and journal evaluation. Developing/live-bar context is labeled separately and must not be mixed with confirmed scanner decisions.

## Frontend integration boundary

The React/Next.js chart page preloads the confirmed compact context from:

```text
GET /api/symbols/{symbol}/decision-context
```

The page renders that VSA Story while the heavier full chart analysis request is still loading. When the full analysis response arrives, the embedded `decision_context` becomes the source for the same panel so the story stays synchronized with the chart payload.

Every rendered VSA Story must visibly label the `DecisionContext.mode` value. Confirmed contexts should be shown as `Confirmed weekly` and described as completed-weekly-bar decision-support context. Developing contexts should be shown as `Developing preview` and described as latest-available weekly data that may change before the week closes and is not a confirmed VSA signal.

Unknown context modes must not be silently treated as confirmed. The frontend should surface an explicit warning when a backend payload contains an unrecognized mode value.

The page also loads read-only decision-journal evaluations from:

```text
GET /api/symbols/{symbol}/decision-journal/evaluations
```

The UI does not pass `persist_status=true`, so viewing journal outcomes does not mutate saved journal status. It may refresh the journal panel after full analysis completes because full analysis can create or update the latest compact journal entry.

The VSA Story and journal panels are decision-support only. They show:

```text
phase
tradability
bias
net pressure
confidence
context mode/status
confirmation condition
invalidation condition
what to expect next
recent smart-money evidence
recent structural swing memory
journal outcome mix
recent validation outcomes
source context week/bar
favorable/adverse post-story move percentages
```

Recent story events can select matching chart evidence or structural swings when the matching bar exists in the full analysis payload. Before the full chart analysis payload arrives, story-event clicks are allowed but may not select a chart marker yet because chart bars/evidence are not loaded.

Recent journal outcomes can also be selected. When chart analysis data is loaded, the page uses source context week/bar metadata to select matching source-bar evidence or structure; if no source-bar match exists, it can fall back to the first checked validation bar. This is only a UI navigation aid.

The frontend panels do not call broker APIs, place orders, size positions, persist journal evaluation status, or change scanner interpretation rules.

## Live validation journal boundary

`decision_journal.py` adds the foundation for comparing a saved confirmed `DecisionContext` with later bars.

The journal stores a compact expectation snapshot, including the story headline, expected next behavior, confirmation/invalidation notes, bias, tradability, and compact support/resistance references from recent structural swing memory.

Validation outcomes are analysis-only labels:

```text
confirmed
invalidated
mixed
pending
observation_only
no_data
```

The journal must not be treated as a trading backtest, strategy profitability report, execution log, or automated decision engine. It is a study aid for reviewing whether the VSA story behaved as expected.

See `docs/live_validation_journal_policy.md` for the detailed journal policy.

## Market data provider boundary

`market_data.py` defines the read-only provider contract used by `data.download_data()`.

The default provider remains yfinance. The provider layer only retrieves raw daily OHLCV payloads; `data.py` still owns normalization, validation, caching, daily-to-weekly resampling, and completed weekly bar filtering.

`UpstoxMarketDataProvider` is present as an explicit read-only daily OHLCV provider. It is not selected automatically, requires explicit enablement, and must not add broker/order scope.

Future providers must not bypass confirmed-bar rules or add broker/order scope.

See `docs/market_data_provider_policy.md` for the detailed provider boundary.

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

This layer is now wired into FastAPI analysis output, local confirmed decision-context persistence, the production incremental scanner path, a cached confirmed decision-context endpoint, a preview-only developing decision-context endpoint, decision-journal creation/list/evaluation APIs, the React/Next.js VSA Story panel with explicit confirmed/developing mode labels, frontend preloading of compact context, frontend read-only journal outcome display, journal-to-chart/context click-through, a read-only market-data provider interface, and an explicit Upstox daily OHLCV provider.

## Future integration path

Recommended follow-up PRs:

1. Add an optional frontend toggle to request the developing preview endpoint, while keeping confirmed context as the default.
2. Add provider/source freshness indicators to the UI.
3. Continue keeping confirmed signals, developing previews, and journal validation separate.
