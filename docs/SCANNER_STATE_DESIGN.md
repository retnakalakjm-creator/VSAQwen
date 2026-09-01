# ProVSA Scanner State Design

**Status:** Proposed / evolving  
**Purpose:** Define the minimum state required for incremental scanning without prematurely implementing persistence.

## 1. Current runtime facts

The active CLI path is:

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

The existing data layer already refreshes a recent `10d` daily window into the local cache. Downstream analysis is still rebuilt from the resulting dataframe, so this is not yet a true persisted market-structure state machine.

## 2. State dependency classification

### A. Must persist for true incremental swing continuation

#### Active swing-search state

`SwingEngine` maintains:

- search state: `TRACKING_HIGH`, `WAITING_HIGH_CONFIRMATION`, `TRACKING_LOW`, or `WAITING_LOW_CONFIRMATION`;
- current candidate bar index;
- candidate week;
- candidate type;
- candidate price.

These values are causally important because an unconfirmed candidate may continue across scanner runs.

#### Confirmed swing boundary

Confirmed swings needed by downstream structural calculations must remain available across the incremental boundary. The current implementation's strongest explicit swing-history requirement is:

- `STRUCTURE_LOOKBACK = 20` swings for structural scoring;
- `TREND_RECENT_SWINGS = 8` swings for trend direction/state context;
- `TREND_STATE_LOOKBACK = 4` swings for trend-state evaluation.

Therefore **20 confirmed swings is currently the dominant explicit swing-history dependency**. This is a swing-count dependency, not yet a fixed number of bars.

#### Last processed closed-bar identity

At minimum:

- symbol;
- timeframe;
- last processed closed-bar timestamp/week identifier.

This establishes the incremental boundary and prevents duplicate processing.

### B. Recalculate from a safety window

The following should generally be recalculated rather than trusted as immutable persisted values:

- swing confirmations near the boundary;
- the active candidate near the boundary;
- recent structural swings;
- recent trend classifications/state;
- recent VSA evidence whose detector depends on boundary bars;
- professional scores for affected recent swings.

A safety window must therefore be large enough to reproduce boundary behavior, not merely large enough to contain the newest bars.

### C. Recompute cheaply from retained bars

The metrics layer currently derives:

- spread;
- body/shadows;
- close ratio;
- previous-bar values;
- rolling average volume/spread;
- standard deviation;
- volume/spread ratios;
- percentile values;
- semantic classifications.

`LOOKBACK_PERIOD = 20` is the current rolling dependency. These values should initially be treated as derived data that can be rebuilt from a sufficient indicator seed window plus the new bars.

### D. Do not persist blindly

Final scanner decisions, professional scores, evidence aggregates, and ranking outputs should not be treated as authoritative causal state. They should be recomputed from persisted causal state and the reopened boundary.

## 3. Swing continuation state

A future incremental swing engine must resume the same logical state as the full sequential calculation.

Conceptually:

```text
Persisted SwingState
├── search_state
├── candidate_bar_identity
├── candidate_type
├── candidate_price
└── confirmed_swing_boundary
```

A candidate's stable timestamp/week identity should accompany any local array index because incremental datasets can be truncated/rebased.

## 4. Confirmed-swing boundary: current conclusion

The boundary has two dimensions:

```text
SWING HISTORY LIMIT
    20 confirmed swings

BAR SAFETY LIMIT
    still to be derived
```

The `20` value comes from the current `STRUCTURE_LOOKBACK` setting and represents the minimum confirmed-swing history explicitly required by structural scoring. It must **not** be translated directly into "20 bars" because swing density is variable.

The bar-based safety window must additionally account for:

- the active swing candidate;
- delayed swing confirmation;
- rolling metric seed requirements;
- evidence detectors with cross-bar dependencies;
- scanner qualification/freshness windows.

## 5. Swing-confirmation dependency

The current swing engine confirms a candidate only after:

- at least `MIN_SWING_CONFIRMATION_BARS = 2` bars since the candidate;
- the reversal threshold is reached;
- two completed bars after the candidate satisfy the structural confirmation test.

This means the most recent bars cannot be treated as final structural history until the confirmation conditions have matured.

The future safety-window calculation should derive its minimum from these rules rather than hard-code an arbitrary 20-bar truncation.

## 6. Indicator seed requirements

`MetricsEngine` uses `LOOKBACK_PERIOD = 20` for rolling volume and spread statistics. Percentile calculation also uses that lookback.

Therefore the incremental acquisition layer needs enough prior **closed** bars to reproduce metric values at the boundary.

Conceptually:

```text
indicator seed
      +
structural safety window
      +
new closed bars
      ↓
reproducible metrics and structure
```

The final combined acquisition window remains open until all evidence dependencies are inventoried.

## 7. Evidence and scanner dependency

The current scanner introduces additional time windows, including:

- `ScannerEngine.SCORING_LOOKBACK_BARS = 10`;
- `ScannerEngine.MAX_ACTIONABLE_VSA_AGE = 3`;
- `ScannerEngine.MIN_REPLAY_BARS = 20`;
- event-specific detector windows configured in `config.py`, including look-aheads for validated patterns such as Shakeout.

Some evidence detectors can inspect bars beyond the event bar during confirmation. Consequently the safety-window analysis must distinguish **causal lookback** from any intentionally validated point-in-time confirmation logic. We should not collapse these dependencies into one arbitrary number.

## 8. Weekly boundary requirement

Daily data is converted to weekly bars using `W-FRI`. The scanner architecture requires closed historical state to remain separate from the current live snapshot.

Future state processing therefore needs to identify:

- last finalized weekly candle;
- current in-progress week, if present;
- whether the weekly bar is eligible for persistent structural state.

An unfinished weekly candle must not silently rewrite finalized historical structure.

## 9. Proposed state envelope

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

## 10. Incremental equivalence contract

Incremental processing is acceptable only after demonstrating:

```text
full-history rebuild
        ==
incremental rebuild from persisted state + safety window
```

The comparison must cover at least:

- confirmed swings;
- candidate/confirmation boundary;
- swing labels;
- trend direction/state/strength/confidence;
- structural swing selection;
- VSA evidence;
- professional scores;
- qualification/actionability;
- final scanner decisions.

## 11. Initial implementation boundary

Do **not** implement persistent storage yet.

The first code slice should instead be a deterministic equivalence harness that can take a dataset, split it at a chosen boundary, and compare:

```text
FULL RUN
vs
PREFIX STATE + REOPENED WINDOW + SUFFIX RUN
```

The harness should tell us exactly which swings/evidence/scores differ. That will empirically determine the required bar safety window before persistence is introduced.

## 12. Current conclusion

The state dependency audit now establishes:

```text
rolling metric dependency     = 20 bars
structural swing history      = 20 confirmed swings
trend structural history      = 8 confirmed swings
trend state history            = 4 confirmed swings
swing confirmation             = minimum 2-bar maturation + structural test
scanner VSA scoring lookback   = 10 bars
scanner actionable VSA age     = 3 bars
```

These numbers are **dependencies**, not a final safety-window constant.

The next engineering target is therefore the **incremental equivalence harness**, not the persistence layer. Once that harness proves what boundary window reproduces the full-history result, the resulting window can become a formal scanner invariant.

## 13. Current implementation references

Relevant modules reviewed while deriving this contract:

- `PROJECT_ARCHITECTURE.md`
- `data.py`
- `metrics_engine.py`
- `trend.py`
- `market_structure/swing_engine.py`
- `market_structure/swing_history.py`
- `market_structure/structure_filter.py`
- `models.py`
- `scanner.py`
- `config.py`
- `engine/columns.py`

The original scanner architecture proposal remains preserved separately in `docs/SCANNER_MODEL_PROPOSAL.md`, with the original external idea set retained in commit `e926e9d8b29f9dda83d8f033dcc2c69e6cf34d79`.

## 14. Empirical audit implications

The VSA event audits add an important state requirement: **decision state cannot be reduced to structural state alone**.

For incremental processing, the boundary must preserve or deterministically reconstruct enough information to reproduce:

- event identity and direction;
- event freshness/age;
- event confirmation status;
- professional score inputs;
- suppression-gate inputs;
- qualification/actionability.

This is particularly important because an event may remain present as evidence while being suppressed from actionability by a regime-specific production gate. Therefore gate state must be causally reproducible at the incremental boundary rather than reconstructed from future outcomes.

`DEMAND_DRYING_UP` also demonstrates why raw event outcomes must not be persisted as decision truth: its raw returns were positive while matched-control incremental deltas were negative. Incremental state should preserve causal evidence and context, not historical outcome-derived labels.

**Decision rule:** persisted/reconstructed state must reproduce the production information boundary, not merely reproduce the final numeric score.

## 15. Current production decision-state contract

The production scoring milestone now freezes four event-specific policies that must be reproducible at an incremental boundary:

| Event | Production state requirement |
| --- | --- |
| `DEMAND_COMING_IN` | Preserve/reconstruct emitted runtime weight `0.38` and the existing `UP + CORRECTING` suppression condition. |
| `INCREASING_DEMAND` | Preserve/reconstruct confirmation-only semantics and the `UP + HEALTHY` sole-bullish actionability gate. |
| `DEMAND_DRYING_UP` | Do not reconstruct it as production evidence; it remains research-only and is not emitted by the production path. |
| `ABSORPTION` | Preserve/reconstruct production connectivity while retaining runtime scoring weight `0.00`; research-only counterfactual penalties must not leak into production state. |

These are decision-layer constraints, not persisted output fields. The incremental engine should reconstruct them from causal state and current production configuration rather than serializing final decisions as authoritative state.

## 16. Regression status

The current production scoring policy is regression-safe under the full repository suite:

```text
python -m pytest -q
210 passed
```

The 210-test result validates the current policy boundary. It does not establish the final bar safety window; that remains an empirical responsibility of the incremental equivalence harness.

## 17. Current engineering boundary

The production scoring/ranking milestone is complete without authorizing a scoring promotion. The next incremental-state work should therefore focus on preserving causal reproducibility of the validated decision path while avoiding unnecessary persistence of derived outputs.
