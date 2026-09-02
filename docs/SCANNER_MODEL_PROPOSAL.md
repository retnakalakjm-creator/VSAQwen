# ProVSA Scanner Model — Living Proposal

**Status:** Proposed / evolving

**Architectural reference:** `e926e9d8b29f9dda83d8f033dcc2c69e6cf34d79` (`Scanner model.txt`)

This document is a working architecture proposal for the future ProVSA scanner. It is intentionally not treated as a final design. The implementation should evolve as we validate data behavior, VSA correctness, state continuity, and operational performance.

## 1. Core principles

- ProVSA is a real-market VSA decision system, not a textbook-pattern detector.
- Preserve strict VSA methodology while allowing imperfect but meaningful real-market evidence.
- Prefer behavior-preserving, measurable architecture changes over speculative optimization.
- Keep historical/scoring logic deterministic and testable.
- Separate closed historical data from the current live market snapshot.

## 2. Proposed high-level scanner flow

```text
Market data source
        ↓
Data acquisition
        ↓
Historical / incremental data store
        ↓
Indicator calculation with required seed window
        ↓
Swing detection
        ↓
Market-structure state update
        ↓
VSA evidence / professional scoring
        ↓
Decision / ranking
        ↓
Scanner report / dashboard
```

## 3. Incremental processing model

The preferred long-term direction is incremental processing rather than rebuilding the full historical pipeline on every scan.

```text
Persisted state + recent safety window + new bars
                    ↓
            recalculate boundary
                    ↓
          update market structure
                    ↓
             process new bars
                    ↓
             persist new state
```

The persisted state may eventually include:

- last processed closed-bar timestamp;
- active market-structure state;
- confirmed swings needed for continuity;
- relevant phase/context state;
- indicator/cache state where safe and useful;
- boundary information required to resume without a full rebuild.

The exact state schema is intentionally left open.

## 4. Safety-window principle

A strict append-only strategy is unsafe for swing-based structure because swing confirmation can occur after the bar where the swing formed.

The scanner should therefore maintain a configurable recent recalculation window:

```text
stored history
      ↓
truncate / reopen recent safety window
      ↓
recalculate boundary + new bars
      ↓
replace the affected recent state
```

The safety-window size should be derived from actual dependencies such as:

- swing confirmation rules;
- trend/state lookbacks;
- rolling VSA metrics;
- other future-look dependency within the causal model.

Avoid hard-coding an arbitrary number until those dependencies are formally established.

## 5. Indicator seed window

New data cannot be processed from the newest candle alone when calculations depend on rolling history.

The acquisition layer should therefore provide enough historical seed data to reproduce the required rolling metrics at the boundary.

```text
new bars
  +
indicator seed window
  ↓
correct rolling metrics
```

The seed length should be derived from the largest required rolling dependency, with an explicit safety margin where necessary.

## 6. Closed data vs live snapshot

The scanner should distinguish between:

### Closed historical dataset

Contains only finalized candles used for persistent historical structure and reproducible backtesting/analysis.

### Live snapshot

Uses the latest available in-progress candle for current dashboard/alert evaluation without allowing that candle to rewrite closed historical structure.

For weekly analysis, the current week must be handled explicitly so an unfinished weekly candle does not contaminate finalized historical structure.

## 7. Data storage direction

The initial implementation may continue using the existing storage approach while the architecture is stabilized.

Longer term, evaluate storage based on actual requirements rather than adopting a format only for theoretical speed. Candidates include:

- Parquet for local analytical storage;
- a time-series database if multi-user/server requirements justify it;
- another compact persistent format if it better fits the scanner lifecycle.

The key requirement is efficient incremental reads/writes with deterministic reconstruction of recent state.

## 8. Parallel ticker processing

After the single-symbol pipeline is stable, ticker-level parallel execution can be introduced:

```text
watchlist
   ↓
worker pool
   ├── symbol A
   ├── symbol B
   ├── symbol C
   └── ...
```

Parallelism should primarily operate at the symbol/job level. It should not change scoring semantics.

Operational constraints to account for:

- data-provider throttling;
- request batching/connection reuse;
- local CPU availability;
- memory pressure;
- persistent-state contention.

Do not assume that maximum CPU parallelism is automatically optimal.

## 9. Scanner execution modes

The future scanner should conceptually support three modes:

### Initial build

One-time full historical acquisition and state construction for a symbol.

### Incremental scan

Use persisted state plus a small recalculation window and newly available closed bars.

### Live evaluation

Evaluate the current in-progress candle separately from persistent closed-bar state.

This separation should prevent live data from silently changing finalized historical structure.

## 10. State and correctness requirements

Any incremental implementation must be equivalent to the relevant full-history calculation at the recalculation boundary.

Validation should compare:

```text
full rebuild result
        vs
incremental result
```

for the same data range.

Important equivalence targets:

- confirmed swings;
- swing types/labels;
- trend state;
- phase/state transitions;
- VSA evidence;
- professional scores;
- structural swing selection;
- final scanner decisions.

Incremental processing should not be accepted merely because it is faster.

## 11. Performance philosophy

The current professional market-structure layer has already undergone targeted optimization and is near the practical threshold for low-risk local micro-optimizations.

Future performance work should therefore prioritize architectural reductions in repeated work:

```text
highest value
─────────────
reduce data loaded
reduce history reprocessed
reuse persisted state
reuse computed indicators
parallelize independent symbols

lower value
───────────
small Python-level micro-optimizations
```

A change should be kept only when it is both correct and measurably useful at end-to-end scanner level.

## 12. Open design questions

This proposal deliberately leaves these unresolved:

- What exact market-structure state must be persisted?
- What is the minimum safe recalculation window for confirmed swings and trend state?
- What is the minimum indicator seed window required by every active metric?
- Which computed arrays are safe to persist versus cheap to rebuild?
- What storage format best fits the actual scanner workflow?
- How should the current live weekly candle interact with active alerts and closed historical state?
- What parallelism model gives the best total throughput without stressing the data provider?
- Should scanner ranking/decision generation happen per symbol or after a cross-symbol aggregation stage?

These should be answered from repository behavior and tests as development continues.

## 13. Architectural reference

The original proposal is preserved in commit:

`e926e9d8b29f9dda83d8f033dcc2c69e6cf34d79`

That commit is a **reference source for ideas**, not an implementation specification.

## 14. Current implementation relationship

Current code should continue to prioritize correctness and stable VSA scoring. The proposed incremental scanner should be introduced around the established scoring engine rather than rewriting validated scoring logic merely to fit the new architecture.

The intended evolution is:

```text
validated scoring engine
        ↓
state-aware scanner orchestration
        ↓
incremental data/state processing
        ↓
parallel symbol execution
        ↓
operational dashboard / alerts
```

This document should be updated whenever an architectural decision is validated, rejected, or materially changed.
