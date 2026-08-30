# ProVSA Scanner State Design

**Status:** Proposed / evolving

**Purpose:** Define the minimum state required for incremental scanning without prematurely implementing persistence. This document is derived from the current repository implementation and is intended to evolve with validated architecture decisions.

## 1. Current runtime facts

The current CLI path is:

```text
Yahoo Finance daily data
        ↓
local CSV cache
        ↓
daily_to_weekly()
        ↓
MetricsEngine.calculate()
        ↓
SwingEngine.calculate()
        ↓
StructureFilter / trend structure
        ↓
EvidenceEngine
        ↓
ProfessionalScoringEngine
        ↓
ScannerEngine qualification / ranking
```

`PROJECT_ARCHITECTURE.md` is the authority for the current system boundaries. The current data layer already refreshes a recent `10d` window into the cached daily history, but the downstream analysis is still rebuilt from the resulting dataframe. This is not yet a true persisted market-structure state machine.

## 2. State dependency classification

### A. Must persist for true incremental swing continuation

#### Active swing-search state

The `SwingEngine` maintains:

- search state: `TRACKING_HIGH`, `WAITING_HIGH_CONFIRMATION`, `TRACKING_LOW`, or `WAITING_LOW_CONFIRMATION`;
- the current candidate swing:
  - candidate bar index;
  - candidate week;
  - candidate type;
  - candidate price.

These values are causally important because an unconfirmed candidate may continue across scanner runs. Reconstructing them incorrectly can change the next confirmed swing.

#### Confirmed swing boundary

The recent confirmed swings required to continue classification and structural analysis must be available. A persisted state should therefore retain at least the confirmed swing sequence that is needed by:

- swing classification;
- trend direction/state;
- structure lookbacks;
- professional structural scoring;
- phase/context dependencies that consume structural history.

The exact number should be derived from downstream dependencies rather than chosen arbitrarily.

#### Last processed closed-bar identity

At minimum:

- symbol;
- timeframe;
- last processed closed-bar timestamp/week identifier.

This establishes the incremental boundary and prevents duplicate processing.

### B. Recalculate from a safety window

The following information should generally be recalculated rather than trusted as immutable persisted values:

- swing confirmations near the boundary;
- the active candidate near the boundary;
- recent structural swings;
- recent trend classifications/state;
- recent VSA evidence whose detector depends on a boundary bar;
- professional scores for affected recent swings.

Reason: swing confirmation is delayed and boundary changes can alter whether a candidate becomes confirmed.

The safety window must therefore extend far enough to cover the largest causal dependency, not merely the latest new bar.

### C. Recompute cheaply from retained bars

The current metrics layer calculates deterministic derived columns such as:

- spread;
- body/shadows;
- close ratio;
- previous-bar values;
- rolling average volume/spread;
- standard deviation;
- volume/spread ratios;
- percentile values;
- classifications.

The current implementation calculates these from the dataframe in `MetricsEngine.calculate()`. Until we establish a persisted metric-state contract, these should be treated as derived data and safely rebuildable from an indicator seed window plus new bars.

### D. Do not persist blindly

Final scanner decisions, professional scores, evidence aggregates, and ranking outputs should not be treated as authoritative state merely because they were produced previously.

They depend on current inputs and recent historical context, so the preferred model is:

```text
persist causal state
        ↓
recalculate affected boundary
        ↓
recompute dependent outputs
```

## 3. Swing continuation state

The current `SwingEngine` starts from a first candidate and processes bars sequentially. A future incremental engine must be able to resume the equivalent logical position.

Conceptually:

```text
Persisted SwingState
├── search_state
├── candidate_bar_index
├── candidate_week
├── candidate_type
├── candidate_price
└── confirmed_swing_boundary
```

However, this is a **logical design**, not yet a final dataclass/API. The candidate's original bar index must remain meaningful relative to the retained/reopened data window, so the persistence format should use stable timestamps/identifiers in addition to local array positions where appropriate.

## 4. Trend state

The current `TrendAnalyzer` derives trend direction and state from classified structural swings. Its state machine is therefore primarily a derived view rather than an independent continuation state.

Current trend outputs include:

- direction;
- state;
- strength;
- confidence;
- swing count;
- classified swings;
- structural swings;
- HH/HL/LH/LL counts.

The incremental design should prefer persisting the confirmed/classified swing boundary and recomputing these trend values. Persisting trend direction alone is insufficient because the underlying swing sequence can change after boundary recalculation.

## 5. Metric seed requirements

`MetricsEngine` currently uses `config.LOOKBACK_PERIOD` for rolling volume and spread calculations. The configured value is `20` in the current repository.

Therefore the future scanner needs enough prior closed bars to reproduce rolling metrics at the incremental boundary. This is the **indicator seed window**, distinct from the structural safety window.

The final acquisition window should satisfy:

```text
indicator seed dependency
+
structural/VSA safety dependency
+
new bars
```

The exact combined window should be calculated once all active downstream dependencies are formally inventoried.

## 6. Weekly boundary requirement

The current data layer downloads daily data and converts it to weekly bars using `W-FRI`. It also explicitly treats the newest daily bar as potentially forming and the scanner architecture calls for closed historical data to remain separate from the live snapshot.

Future state processing must therefore identify:

- last finalized weekly candle;
- current in-progress week, when present;
- whether a weekly bar is eligible for persistent structural state.

An unfinished weekly candle must not silently rewrite finalized historical structure.

## 7. Proposed state envelope

A future persisted state is likely to resemble:

```text
ScannerState
├── schema_version
├── symbol
├── timeframe
├── last_closed_bar
├── swing_state
│   ├── search_state
│   ├── candidate
│   └── confirmed_swing_boundary
├── structural_context
│   └── retained causal swing history
├── metric_state
│   └── only if later proven cheaper/safer than recomputation
└── state_metadata
```

This is intentionally smaller than a serialized copy of the entire scanner output.

## 8. Incremental equivalence contract

The scanner may adopt incremental processing only after demonstrating:

```text
full-history rebuild
        ==
incremental rebuild from persisted state + safety window
```

The comparison must cover at least:

- confirmed swings;
- swing candidate/confirmation boundary;
- swing labels;
- trend direction/state/strength/confidence;
- structural swing selection;
- VSA evidence;
- professional scores;
- qualification/actionability;
- final scanner decisions.

A faster result that changes any of these unexpectedly is not an acceptable optimization.

## 9. Initial implementation boundary

The first implementation should **not** attempt to persist everything.

Recommended first slice:

```text
ScannerState
    ↓
last closed bar
    +
swing continuation state
    +
minimum confirmed swing boundary
```

Then build a test harness that runs:

```text
full scan
vs
incremental scan
```

on controlled datasets with bars added one at a time.

Only after equivalence is demonstrated should we add persistent metric caches, storage-format changes, or ticker-level parallel execution.

## 10. Current implementation references

Relevant current modules reviewed while deriving this contract:

- `PROJECT_ARCHITECTURE.md`
- `data.py`
- `metrics_engine.py`
- `trend.py`
- `market_structure/swing_engine.py`
- `market_structure/swing_history.py`
- `models.py`
- `scanner.py`
- `config.py`
- `engine/columns.py`

The original scanner architecture proposal remains preserved separately in `docs/SCANNER_MODEL_PROPOSAL.md`, with the original external idea set retained in commit `e926e9d8b29f9dda83d8f033dcc2c69e6cf34d79`.

## 11. Open questions before implementation

- What is the minimum confirmed-swing history required by every active downstream consumer?
- Should persisted candidate positions use absolute bar timestamps rather than array indices?
- What exact weekly close rule should be shared by acquisition and state persistence?
- Which evidence/phase engines contain additional cross-bar state that must be represented?
- Can rolling metrics be safely reconstructed from a seed window in every case, or are any statistics stateful enough to justify persistence?
- What state versioning/migration strategy is required before persistent files are introduced?

**Decision rule:** derive these answers from the active implementation and equivalence tests, not from arbitrary constants.