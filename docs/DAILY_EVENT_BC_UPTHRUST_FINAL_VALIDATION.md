# M12 / L18 — Final BUYING_CLIMAX / UPTHRUST Validation

## Purpose

L18 is the final permitted validation stage for the redesigned:

    BUYING_CLIMAX
    UPTHRUST

semantic candidates.

The detector definitions are frozen before L18 begins.

No new threshold search is allowed.

No new candidate definition is allowed.

No forward-return optimization is performed.

After L18 the decision must be:

    PROMOTE
    REJECT
    or
    PARK

There is no default L19 research layer for this pair.

## Frozen candidates

### BUYING_CLIMAX exhaustion candidate

Frozen from L17:

    canonical current BUYING_CLIMAX effort core
    AND
    close-position acceptance is NOT strong-high acceptance

Equivalent acceptance buckets:

    MIDDLE
    LOWER
    ON_LOW

Excluded:

    UPPER
    ON_HIGH

Canonical frozen count:

    887

This is the semantic candidate:

    climactic buying effort
    +
    deteriorating / non-strong high-price acceptance

It is not chosen from forward outcomes.

### UPTHRUST structural rejection candidate

Frozen from L17:

    current high
        >
    latest causally confirmed structural swing-high price

    AND

    current close
        <=
    that structural swing-high price

Canonical frozen count:

    10,526

This is the semantic candidate:

    probe above meaningful confirmed resistance
    +
    failure to hold above it

The rejected local previous-high definition is not reconsidered in L18.

## Source

L18 consumes only the canonical L17 output directory.

Required files:

    daily_bc_upthrust_semantic_summary.json
    daily_bc_upthrust_semantic_observations.csv
    daily_bc_upthrust_semantic_symbols.csv

L18 does not replay market data.

It fingerprints all three source artifacts.

## Hard source gates

L18 requires the canonical L17 source to remain:

    audit_id
        daily-event-bc-upthrust-semantic-replay-v1

    requested symbols
        30

    succeeded symbols
        30

    failed symbols
        0

    evaluated targets
        198,382

    canonical BC effort core
        4,497

    structural UPTHRUST candidate
        10,526

    BC identity mismatch
        0

    L17 actionable
        false

The final frozen candidate identities must reconcile to:

    BC exhaustion candidate
        887

    UT structural rejection candidate
        10,526

    same-bar overlap
        129

If those identities change, the L18 question is stale.

## Validation dimension 1 — cross-symbol robustness

L18 reports, for every symbol:

    evaluated target count

    BC candidate count
    BC candidate rate

    UT candidate count
    UT candidate rate

    same-bar overlap count

It also summarizes each candidate across symbols:

    total event count
    symbol coverage
    minimum symbol count
    median symbol count
    maximum symbol count

    minimum symbol rate
    median symbol rate
    maximum symbol rate

    maximum one-symbol share of all candidate events

This is a representation / concentration check.

It does not rank symbols.

## Validation dimension 2 — cross-era robustness

The same fixed calendar eras are used:

    EARLY_HISTORY
    2010_2014
    2015_2019
    2020_2022
    2023_2026

For each candidate and era L18 reports:

    event count
    share of candidate history
    symbol count

No era is interpreted as a semantic regime.

The purpose is simply to ensure that a proposed production concept is not a
one-era artifact.

Expected row count:

    2 candidates
    x
    5 eras
    =
    10 rows

## Validation dimension 3 — identity partition

Every frozen candidate event belongs to:

    BC_ONLY
    UT_ONLY
    BOTH

The same-bar BOTH group is retained explicitly.

The redesigned labels are allowed to overlap.

The goal is not forced mutual exclusivity.

The key question is whether they remain meaningfully distinct.

Canonical identities already frozen from L17:

    BC candidate
        887

    UT candidate
        10,526

    same-bar overlap
        129

Therefore expected derived partition totals are:

    BC_ONLY
        758

    UT_ONLY
        10,397

    BOTH
        129

    union
        11,284

These are identity invariants, not predictive results.

## Validation dimension 4 — behavior-sequence usefulness

The existing DailyBehaviorSequence audit uses:

    lookback_bars = 5

That means two distinct behavior observations can coexist in one bounded
sequence when their positive bar-index offset is:

    1
    2
    3
    or
    4

L18 therefore measures exactly two ordered relationships:

    BC_TO_UT

        BC exhaustion candidate
        followed by
        structural UPTHRUST candidate

    UT_TO_BC

        structural UPTHRUST candidate
        followed by
        BC exhaustion candidate

Same-bar overlap is not counted as an ordered transition.

For each direction L18 reports:

    source event count
    source events followed by target within 4 bars
    source-with-target rate
    ordered pair count
    symbol count
    median positive offset

It also reports:

    pair count by offset 1 / 2 / 3 / 4

and:

    source / transition coverage by fixed era

This is a temporal distinctness check.

It does not claim that one order is bullish, bearish, predictive, or superior.

## Current behavior-layer collision

Current DailyBehavior mapping still maps both:

    BUYING_CLIMAX
    UPTHRUST

under bearish WeeklySetup to:

    REJECTION_OF_OPPOSING_MOVE

L18 hard-validates and reports this.

Therefore even if the detector semantic candidates validate successfully:

    production detector semantics
        can become distinct

while:

    current behavior-dimension mapping
        would still collapse both names into one dimension

That is an architectural finding.

It does not invalidate the candidates.

It means later DailyBehavior recalibration may be required if ProVSA needs to
preserve the distinction:

    climactic effort / exhaustion

versus:

    structural rejection of higher prices

inside the higher-level narrative.

L18 does not change DailyBehavior.

## Why no forward-outcome study here

The purpose of this detector cleanup is:

    mechanically correct
    semantically interpretable
    meaningfully distinct

event vocabulary.

An individual event does not need to be a profitable standalone signal in order
to be useful inside:

    bar-by-bar behavior progression
    effort/result interpretation
    supply/demand narrative
    acceptance/rejection sequence reasoning

Forward-return optimization at this stage would risk selecting a historical
subgroup instead of validating the concept.

## Outputs

    daily_bc_upthrust_final_summary.json
    daily_bc_upthrust_final_symbols.csv
    daily_bc_upthrust_final_symbol_summary.csv
    daily_bc_upthrust_final_eras.csv
    daily_bc_upthrust_final_partitions.csv
    daily_bc_upthrust_final_transitions.csv
    daily_bc_upthrust_final_transition_offsets.csv
    daily_bc_upthrust_final_transition_eras.csv
    daily_bc_upthrust_final_behavior_mapping.csv

## Local validation

    python -m ruff check audit/daily_event_bc_upthrust_final_validation.py scripts/audit_daily_event_bc_upthrust_final_validation.py tests/test_daily_event_bc_upthrust_final_validation.py

    python -m pytest -q tests/test_daily_event_bc_upthrust_final_validation.py tests/test_daily_event_bc_upthrust_semantic_replay.py tests/test_daily_behavior_sequence_outcomes.py

## Canonical input

Default L17 output from the frozen run:

    reports\daily-events\bc-upthrust-semantic-replay\milestone6_standard_india_large_cap_30\2026-09-18

## Canonical run

    python scripts/audit_daily_event_bc_upthrust_final_validation.py --input-dir reports\daily-events\bc-upthrust-semantic-replay\milestone6_standard_india_large_cap_30\2026-09-18

## Fixed top-level expectations

    requested_symbol_count              30
    evaluated_target_count          198382

    bc_candidate_count                 887
    ut_candidate_count               10526

    same_bar_overlap_count             129
    bc_only_count                      758
    ut_only_count                    10397
    candidate_union_count            11284

    era_count                            5
    sequence_lookback_bars               5

    current_behavior_mapping_collapsed  true

    symbol_row_count                    30
    symbol_summary_row_count             2
    era_row_count                       10
    partition_row_count                  3
    transition_row_count                 2
    transition_offset_row_count          8
    transition_era_row_count            10
    behavior_mapping_row_count           2

    is_actionable                    false

Transition counts themselves are findings, not fixed expectations.

## Final decision rule

After L18 there are no more exploratory detector-definition stages.

### PROMOTE

A candidate may proceed to a production correction PR when:

- it remains represented across the full symbol basket;
- it remains represented across historical eras;
- it remains meaningfully distinct from the other candidate;
- its observed geometry matches the frozen semantic concept;
- no implementation or causal defect is discovered.

Promotion means:

    implement the already-frozen semantic contract

not:

    tune it further.

### REJECT

Reject a candidate if final validation shows that:

- it is concentrated in a tiny symbol / era subset;
- it collapses back into the neighboring detector;
- its temporal behavior contradicts the intended semantic role;
- or its source lineage / causality fails.

### PARK

Park when the concept remains plausible but evidence is too sparse or unstable
for a production contract.

## Production boundary

L18 itself changes no:

- BUYING_CLIMAX collector;
- UPTHRUST collector;
- confirmation gating;
- weights;
- professional supply score;
- ranking;
- DailyBehavior;
- weekly thesis;
- qualification/actionability;
- API;
- alert;
- order;
- production market-data loading.

Its only purpose is to force a final evidence-based decision for the frozen
semantic candidates.
