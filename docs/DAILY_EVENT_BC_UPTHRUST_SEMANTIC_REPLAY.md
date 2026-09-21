# M12 / L17 — BUYING_CLIMAX / UPTHRUST Causal Semantic Replay

## Purpose

L16 froze a first-principles semantic redesign for the production pair:

    BUYING_CLIMAX
    UPTHRUST

L17 performs the single causal replay allowed by that design.

It does not use forward outcomes, tune thresholds, or change production.

The replay asks only:

1. what acceptance geometry exists inside the current BUYING_CLIMAX effort core;
2. how common a threshold-free previous-high rejection definition is;
3. how common a causally confirmed structural-high rejection definition is;
4. whether those redesigned populations are meaningfully distinct rather than aliases.

## Source foundation

L17 uses the canonical frozen 30-symbol daily input bundle:

    milestone6_standard_india_large_cap_30
    period = max
    cutoff = 2026-09-18

and the canonical L3 confirmation ledger.

The L3 BUYING_CLIMAX firing set is used as an exact parity authority.

Canonical baseline:

    BUYING_CLIMAX = 4,497 events
    symbols       = 30

## Point-in-time replay

Metrics are computed from the frozen daily history using the existing MetricsEngine.
All MetricsEngine transformations used here are trailing / shifted historical calculations.

For structure, L17 performs one SwingEngine + StructureFilter pass per symbol.

This is safe for the semantic replay because StructureFilter's contract states
that a confirmed swing's professional evaluation depends only on that swing
and earlier point-in-time history.

Causality is then enforced explicitly at each target bar.

A structural reference high is eligible only when:

    swing.type == HIGH
    confirmation_index <= target_index
    pivot bar_index < target_index

Therefore a future-confirmed high cannot become the target bar's reference.

## Population 1 — BUYING_CLIMAX effort core

L17 uses the canonical L3 BUYING_CLIMAX identity ledger as production authority.

For every one of those identities it verifies:

    exact symbol
    exact bar index
    exact session
    Bullish Bar
    Very High Volume
    Above Average Spread

The Buying Campaign requirement is inherited from the already-validated
production emission ledger rather than recomputed for every bar.

Required full-run parity:

    baseline BC events           4,497
    replay BC events             4,497
    BC identity mismatches           0

If this fails, L17 is not interpretable.

## BUYING_CLIMAX acceptance geometry

The 4,497 effort-core bars are partitioned without inventing a threshold.

Existing production ClosePosition buckets define:

    STRONG_HIGH_ACCEPTANCE
        UPPER
        ON_HIGH

    MIDDLE_ACCEPTANCE
        MIDDLE

    WEAK_LOWER_ACCEPTANCE
        LOWER
        ON_LOW

This answers whether the current BUYING_CLIMAX label combines strong high-price acceptance with actual poor high-price acceptance / exhaustion geometry.

L17 does not decide which bucket should become mandatory.

## Population 2 — UPTHRUST local rejection

Predeclared L16 local definition:

    current.high > previous.high
    AND
    current.close <= previous.high

Interpretation:

    price probed above the previous bar's high
    but failed to hold above that reference by the close

This is intentionally threshold-free.

It does not require Bullish Bar, Very High Volume, Wide Spread, or Buying Campaign.
Those fields are measured as descriptors rather than silently inherited from the current collapsed detector.

## Population 3 — UPTHRUST structural rejection

Predeclared L16 structural definition:

    current.high > latest confirmed structural swing-high price
    AND
    current.close <= that structural swing-high price

The reference is the latest structural HIGH already causally confirmed by the target bar.

This tests rejection at a meaningful structural higher-price reference rather than merely a two-bar reversal.

## Descriptor policy

For BC core, local UT, and structural UT populations L17 records:

    bar direction
    volume class
    spread class
    close position

and continuous descriptive geometry:

    close ratio
    upper-shadow / spread ratio
    volume ratio
    spread ratio

No descriptor is promoted into a gate in L17.

Campaign/trend/state descriptors were deliberately removed from L17 after
performance review because they are not needed to answer the semantic identity
question and would require expensive per-bar context reconstruction.

## Pairwise identity audit

L17 compares:

    BC core vs UT local
    BC core vs UT structural
    UT local vs UT structural

and reports counts, overlap, union, Jaccard, and relationship.

Relationship classes:

    IDENTICAL_FIRING_SET
    DISJOINT
    A_STRICT_SUBSET_OF_B
    B_STRICT_SUBSET_OF_A
    PARTIAL_OVERLAP

The semantic redesign expects the BC/UT relationships to become PARTIAL_OVERLAP.
They do not need to be disjoint.

## Canonical hard gates

Known before the run:

    requested_symbol_count          30
    succeeded_symbol_count          30
    failed_symbol_count              0

    baseline_bc_event_count       4,497
    replay_bc_event_count         4,497
    bc_identity_mismatch_count        0

    population_row_count              3
    bc_acceptance_row_count           3
    pairwise_row_count                3
    symbol_row_count                 30
    failure_row_count                 0

    is_actionable                 false

Unknown before replay:

    evaluated_target_count
    structural_reference_available_count
    BC acceptance bucket counts
    UT local rejection count
    UT structural rejection count
    descriptor row count
    observation row count
    pairwise overlap / Jaccard / relationships

These are findings, not expected constants.

## Outputs

    daily_bc_upthrust_semantic_summary.json
    daily_bc_upthrust_semantic_populations.csv
    daily_bc_acceptance_geometry.csv
    daily_bc_upthrust_semantic_descriptors.csv
    daily_bc_upthrust_semantic_pairwise.csv
    daily_bc_upthrust_semantic_symbols.csv
    daily_bc_upthrust_semantic_observations.csv
    daily_bc_semantic_parity_mismatches.csv
    daily_bc_upthrust_semantic_failures.csv

## Local validation

    python -m ruff check audit/daily_event_bc_upthrust_semantic_replay.py scripts/audit_daily_event_bc_upthrust_semantic_replay.py tests/test_daily_event_bc_upthrust_semantic_replay.py

    python -m pytest -q tests/test_daily_event_bc_upthrust_semantic_replay.py tests/test_daily_event_bc_upthrust_identity_separation.py tests/test_daily_event_confirmation_semantics.py

## Canonical run

    python scripts/audit_daily_event_bc_upthrust_semantic_replay.py --confirmation-dir reports\daily-events\confirmation-counterfactual\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --input-snapshot-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30\2026-09-18 --now 2026-09-18T16:00:00+05:30

## Interpretation order

### 1. BC parity

Must be exact. If not, stop and fix replay before interpreting semantic populations.

### 2. BUYING_CLIMAX acceptance split

Ask whether the current 4,497-event effort core contains a substantial strong-acceptance population.

If yes, the current label is likely mixing high-volume continuation with exhaustion / poor acceptance.

If almost all BC-core bars already close poorly, the missing BC distinction may be smaller than expected.

### 3. UPTHRUST population representation

Ask separately whether local and structural rejection are sufficiently represented and span many symbols.

A definition that collapses to a tiny handful of events should be rejected or parked rather than loosened post hoc.

### 4. BC / UT overlap

Desired semantic relationship:

    PARTIAL_OVERLAP

If rejection populations remain nearly identical to BC, redesign failed.

If they are represented, distinct, and partially overlapping, semantic replay succeeded.

### 5. Descriptor sanity

UPTHRUST is a rejection concept. L17 therefore measures whether the population naturally contains bullish bars, bearish bars, different volume classes, and different close positions without using them as selectors.

This helps determine whether the old mandatory Bullish Bar and Very High Volume requirements were describing the event or defining it too narrowly.

## Stop rule

L17 is the semantic replay promised by L16.

After canonical interpretation there are only two paths.

### Semantic replay fails

Examples:

- UT definitions are too rare;
- populations are still aliases;
- structural reference coverage is inadequate;
- geometry does not create a coherent distinct vocabulary.

Decision:

    REJECT or PARK

Then move to the next detector. No threshold search.

### Semantic replay succeeds

Requirements:

- exact BC parity;
- UT population sufficiently represented across symbols;
- BC and UT meaningfully distinct;
- geometry matches intended concepts.

Then exactly one final validation stage is allowed.

That final stage should evaluate robustness and/or usefulness inside behavior sequences, not search for a better definition.

After that:

    PROMOTE
    REJECT
    or
    PARK

No third exploratory layer.

## Relationship to the ProVSA goal

This replay is not trying to make either detector a standalone profitable trade signal.

Its purpose is to produce a trustworthy event vocabulary for higher-level reasoning.

A future sequence should be able to distinguish:

    buying effort became climactic

from:

    higher prices were rejected

so ProVSA can build narratives such as:

    strong markup
    -> climactic effort
    -> failed acceptance at higher prices
    -> supply gaining control

without double-counting two names for the same mechanical event.

## Safety

L17 changes no BUYING_CLIMAX or UPTHRUST production contract, confirmation gate, evidence weight, supply score, scanner ranking, weekly thesis, DailyBehavior, qualification/actionability, API, alert, order, or production data loading.
