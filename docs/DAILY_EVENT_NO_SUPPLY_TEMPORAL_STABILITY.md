# M12 / L11 — NO_SUPPLY WEAK_RESULT_ONLY Temporal Stability

## Purpose

L10 established two important facts about the fixed `WEAK_RESULT_ONLY`
candidate:

1. close-to-close return lift is not yet robust enough under a 30-symbol
   cluster bootstrap;
2. favorable excursion (MFE) is much more robust, especially over H1-H5.

L11 asks whether that behavior is stable across time.

The core question is:

    does the same candidate behave similarly in different historical periods,
    or is the full-history result being carried by one unusual era?

L11 performs no market-data, detector, swing, structure, or trend replay.

It reuses:

- the canonical L10 candidate target ledger;
- the canonical L8 matched pair-outcome ledger.

## Plain-English interpretation

Suppose a setup appears 100 times and looks profitable overall.

That is not enough.

If 80 of the good reactions happened during one unusual market period, such as
a major crash/rebound regime, the setup may not be generally reliable.

L11 therefore cuts history into separate non-overlapping time blocks and asks:

    did the setup still show the same behavior in each block?

It also asks:

    if we completely remove one era, does the full-history conclusion survive?

That is a durability test.

## Fixed candidate definition

L11 does not rediscover or redefine the candidate.

It hard-validates that every candidate row remains:

    stratum == WEAK_RESULT_ONLY

with:

    weak_selling_result = true
    volume_decreasing   = false

Source semantics remain:

    is_weak_close(bar)
    AND NOT volume_decreasing(bar, previous)

with mandatory production NO_SUPPLY requirements still including:

    Bearish Bar
    Low Volume
    Narrow Spread

L11 is therefore studying exactly the same 427-event population established in
L9/L10.

## Canonical population

    CURRENT / DOWN      122
    ALTERNATE / UP      305
    total               427
    symbols              30

## Era definitions

The eras are fixed in code before outcome inspection.

They are not chosen from the observed results.

    EARLY_HISTORY
        all candidate history through 2009

    2010_2014
        2010 through 2014

    2015_2019
        2015 through 2019

    2020_2022
        2020 through 2022

    2023_2026
        2023 through 2026

These are calendar partitions, not inferred market labels.

In particular, L11 does not call any era:

    bull market
    bear market
    COVID regime
    recovery regime

Those interpretations would require a separate regime-classification study.

## Why fixed calendar eras

Using fixed periods avoids an important research mistake:

    choosing time buckets after seeing where the signal performs well.

L11 therefore accepts unequal event counts and unequal symbol coverage across
eras.

Those differences are themselves part of the evidence.

## Source lineage

L11 fingerprints and validates exact:

- L10 summary;
- L10 candidate-target ledger;
- L10 robustness output;
- L10 cluster-bootstrap output;
- L10 leave-one-symbol-out output;
- L10 semantic truth table;
- L8 summary;
- L8 matched pair outcomes;
- inherited frozen snapshot manifest.

Hard gates include:

    L10 candidate targets            427
    CURRENT                          122
    ALTERNATE                        305
    symbols                           30
    L8 matched targets             2,509
    L8 pair rows                  12,539

Every candidate pair must preserve:

    symbol
    target session
    cohort
    trend direction
    bar index
    era assignment

## Era count ledger

For every:

    era
    cohort

L11 reports:

    source target count
    symbol count
    first target session
    last target session

Expected row count:

    5 eras x 2 cohorts = 10

This makes sparse historical periods visible before interpreting performance.

## Era outcome ledger

For every non-empty:

    era
    cohort
    horizon

L11 reports clean matched deltas for:

    return
    positive-close rate
    MFE
    MAE

using both:

    EVENT_WEIGHTED
    SYMBOL_NORMALIZED

It also reports:

    source target count
    complete pair count
    clean pair count
    symbol count
    positive / negative / zero return-symbol breadth

The sign convention remains:

    TARGET - CONTROL

Positive MFE delta means the candidate target achieved more favorable excursion
than its matched same-symbol, same-environment bearish control.

Positive MAE delta means less adverse excursion because MAE is <= 0.

## Temporal consistency ledger

For every:

    cohort
    horizon
    metric
    estimand

L11 counts how many available eras are:

    positive
    negative
    zero

and records:

    weakest era
    weakest era value
    strongest era
    strongest era value

Expected row count:

    2 cohorts
    x 5 horizons
    x 4 metrics
    x 2 estimands
    = 80

This makes temporal sign stability explicit.

Example:

    H3 MFE:
        5 positive eras
        0 negative eras

would be much stronger temporal evidence than:

    H3 MFE:
        2 positive eras
        3 negative eras

even if both had a positive full-history mean.

## Leave-one-era-out return test

L11 also removes each entire era and recomputes full-history return lift.

For every:

    cohort
    horizon
    estimand
    omitted era

it reports:

    original full-history return delta
    return delta after omitting the era
    shift from full estimate
    remaining clean-pair count
    remaining symbol count
    whether the estimate remains positive

Expected row count:

    2 cohorts
    x 5 horizons
    x 2 estimands
    x 5 omitted eras
    = 100

This answers:

    is one time period carrying the full-history result?

If removing one era flips the sign, the candidate is temporally fragile.

## What L11 can and cannot establish

L11 can show whether the fixed candidate's behavior is stable across broad
calendar periods.

It does not prove that the candidate is stable across:

- volatility regimes;
- market phases;
- macroeconomic regimes;
- sectors;
- index membership changes;
- structural market microstructure changes.

Those require explicit regime/state classification.

## Expected fixed top-level invariants

    requested_symbol_count              30
    candidate_target_count             427
    current_candidate_target_count     122
    alternate_candidate_target_count   305

    era_count                            5
    era_count_row_count                 10

    horizon_count                        5
    horizons                        1,3,5,10,20

    consistency_row_count               80
    leave_one_era_out_row_count        100

    is_actionable                    false

Era-outcome row count is measured because a cohort/era could theoretically
contain no candidate targets.

## Outputs

    daily_no_supply_temporal_stability_summary.json
    daily_no_supply_temporal_candidate_targets.csv
    daily_no_supply_temporal_era_definitions.csv
    daily_no_supply_temporal_era_counts.csv
    daily_no_supply_temporal_era_outcomes.csv
    daily_no_supply_temporal_consistency.csv
    daily_no_supply_temporal_leave_one_era_out.csv

## Local validation

    python -m ruff check audit/daily_event_no_supply_temporal_stability.py scripts/audit_daily_event_no_supply_temporal_stability.py tests/test_daily_event_no_supply_temporal_stability.py

    python -m pytest -q tests/test_daily_event_no_supply_temporal_stability.py tests/test_daily_event_no_supply_weak_result_robustness.py

## Canonical run

    python scripts/audit_daily_event_no_supply_temporal_stability.py --robustness-dir reports\daily-events\no-supply-weak-result-robustness\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --matched-dir reports\daily-events\no-supply-matched-environment\milestone6_standard_india_large_cap_30_frozen_2026-09-18

## Interpretation focus

Because L10's strongest finding was early favorable excursion rather than
terminal return, L11 should pay special attention to:

    H1 MFE
    H3 MFE
    H5 MFE

for both:

    CURRENT / DOWN
    ALTERNATE / UP

The strongest temporal result would be:

- MFE delta positive in most or all eras;
- both event-weighted and symbol-normalized views agree;
- no single era carries the full-history effect;
- return behavior does not become strongly adverse in the same periods;
- sufficient candidate/symbol coverage exists in each era.

If MFE is strong only in one era, L10's apparent robustness is not temporally
general.

## Safety

L11 changes no:

- NO_SUPPLY requirements;
- environment predicate;
- confirmation labels;
- confirmation gates;
- evidence weights;
- scoring/ranking;
- DailyBehavior;
- qualification/actionability;
- API behavior;
- alerts/orders;
- production data loading.
