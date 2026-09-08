# Live Validation Journal Policy

## Purpose

The live validation journal is a compact decision-support record that connects a saved VSA story with what later bars actually did.

It answers a practical question for the local ProVSA Command Centre:

```text
The scanner expected this behavior.
What happened after that?
Was the story confirmed, invalidated, mixed, or still pending?
```

This is not a trading journal, not an order log, and not a full historical event database.

## What the journal stores

Each journal entry is created from one `DecisionContext` and stores only the decision-relevant expectation:

```text
symbol / timeframe
source context week and bar index
phase
bias
tradability
decision label
confidence
net pressure
headline and summary
confirmation condition
invalidation condition
expected next behavior
latest compact support / resistance references from structural swing memory
```

The journal intentionally does not persist all historical VSA events, all bars, all candidates, tick data, broker credentials, orders, positions, or trade execution requests.

## Validation model

`evaluate_journal_entry()` compares one journal entry with later OHLCV bars after the source context bar.

The default validation horizon is 8 bars.

Outcomes are deliberately conservative:

```text
confirmed
invalidated
mixed
pending
observation_only
no_data
```

For bullish contexts, confirmation means a later close clears the compact resistance/reference level; invalidation means a later close loses the compact support/reference level.

For bearish contexts, confirmation means a later close breaks the compact support/reference level; invalidation means a later close recovers above the compact resistance/reference level.

If both confirmation and invalidation occur inside the checked window, the result is `mixed` and must be reviewed manually.

Mixed, neutral, and avoid contexts are tracked as `observation_only` because they should not be treated as directional setup validation.

## API persistence behavior

FastAPI creates or updates a compact journal entry whenever a confirmed `DecisionContext` is freshly rebuilt through the API analysis path.

This includes:

```text
GET /api/symbols/{symbol}/analysis
GET /api/symbols/{symbol}/decision-context when the cached context is missing, invalid, developing-mode, or stale
```

A fresh cached decision-context response does not create a new journal entry because no new analysis was performed and the stored context is already current.

The service uses `DecisionJournalStore.upsert()` so the same source context identity updates the existing journal entry instead of creating duplicates.

Journal persistence is enabled by default in the local API service and can be disabled or redirected in tests by passing `persist_decision_journal=False` or a temporary `DecisionJournalStore`.

## API list and evaluation behavior

FastAPI exposes journal read/evaluation endpoints:

```text
GET /api/symbols/{symbol}/decision-journal
GET /api/symbols/{symbol}/decision-journal/evaluations
```

The list endpoint returns saved compact journal entries only. It does not run scanner analysis and does not download fresh chart payloads beyond normal API routing.

The evaluation endpoint compares saved journal entries with completed weekly bars and returns `DecisionJournalEvaluation` payloads. Evaluation is read-only by default so viewing the journal does not mutate saved status.

To explicitly save evaluation outcomes back into the journal, callers must pass:

```text
persist_status=true
```

The evaluation endpoint accepts `horizon_bars`; invalid values such as zero or negative horizons are rejected.

## Financial correctness boundary

The journal is analysis-only.

It does not change:

```text
scanner execution logic
VSA detectors
scoring weights
thresholds
ranking
qualification
actionability
API analysis output
frontend decisions
broker integration
order placement
position sizing
```

The validation outcome is a study aid for improving market reading. It must not be interpreted as a backtest result or used as automatic trading logic.

## Current implementation

`decision_journal.py` adds:

```text
BarObservation
DecisionJournalEntry
DecisionJournalEvaluation
DecisionJournalStore
ValidationOutcome
create_journal_entry
evaluate_journal_entry
```

`DecisionJournalStore` persists compact journal files under:

```text
state/decision_journal/
```

The store uses atomic JSON writes and deterministic entry IDs so the same context can be safely upserted instead of duplicated.

`api.service.ProVSAService` can receive an injected `DecisionJournalStore` and persistence flag for tests/local customization. It can now list saved journal entries and evaluate them against completed weekly bars.

## Future integration path

Recommended follow-up PRs:

1. Render journal entries and evaluation outcomes in the React/Next.js VSA Story panel.
2. Add developing/live-bar validation later, clearly separated from confirmed weekly signals.
3. Add market-data provider abstractions before any Upstox read-only data source is introduced.

No broker order scope should be added to this feature.
