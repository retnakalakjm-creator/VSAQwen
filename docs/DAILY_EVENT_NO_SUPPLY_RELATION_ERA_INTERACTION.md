# M12 / L13 — ALTERNATE VolumeClass Relation × Era Interaction

## Purpose

L12 identified the strongest current context hypothesis for the ALTERNATE/UP
`WEAK_RESULT_ONLY` population:

    SAME_CLASS
        current VolumeClass == previous VolumeClass

became more common in 2023-2026 and historically has weaker H1/H3/H5 MFE than:

    HIGHER_CLASS
        current VolumeClass > previous VolumeClass

However, the composition shift was far too small to explain the full recent
ALTERNATE breakdown.

L13 asks a narrower question:

    Did both VolumeClass-relation groups fail in 2023-2026,
    or is the failure concentrated in SAME_CLASS?

No new detector replay is required.

L13 consumes the fixed L12 context ledger and the canonical L8 matched outcome
ledger.

## Plain-English interpretation

Suppose older ALTERNATE events look like this:

    SAME_CLASS
        H3 MFE +0.25%

    HIGHER_CLASS
        H3 MFE +0.75%

and the latest period looks like:

    SAME_CLASS
        H3 MFE -0.20%

    HIGHER_CLASS
        H3 MFE +0.60%

Then the failure is concentrated in SAME_CLASS.

That would make the VolumeClass relation a stronger conditional hypothesis.

But if latest history looks like:

    SAME_CLASS
        H3 MFE -0.20%

    HIGHER_CLASS
        H3 MFE -0.30%

then BOTH groups failed.

In that case, the recent ALTERNATE breakdown is broader than this confirmation
relationship and we should keep looking for a higher-level state.

## Fixed source population

Canonical L12 ALTERNATE population:

    total                       305

    SAME_CLASS                  201
    HIGHER_CLASS                104

Prior history through 2022:

    SAME_CLASS                  170
    HIGHER_CLASS                 93

2023-2026:

    SAME_CLASS                   31
    HIGHER_CLASS                 11

L13 hard-validates all of these counts.

## Correct VolumeClass semantics

Production:

    volume_decreasing(current, previous)

compares:

    BarContext.volume

which is a `VolumeClass` enum.

Therefore:

    SAME_CLASS
        current VolumeClass ordinal
        == previous VolumeClass ordinal

    HIGHER_CLASS
        current VolumeClass ordinal
        > previous VolumeClass ordinal

L13 hard-validates:

    SAME_CLASS -> volume_class_delta == 0
    HIGHER_CLASS -> volume_class_delta > 0

and rejects negative deltas.

It also validates:

    era == 2023_2026
        <=> comparison_group == ALTERNATE_2023_2026

All older rows must use:

    ALTERNATE_PRIOR_THROUGH_2022

## Era grid

L13 keeps the same five fixed calendar eras:

    EARLY_HISTORY
    2010_2014
    2015_2019
    2020_2022
    2023_2026

For each era it keeps the two relation groups separate:

    SAME_CLASS
    HIGHER_CLASS

This creates:

    5 eras x 2 relations = 10 count cells

Every cell reports:

    source target count
    symbol count
    first session
    last session

Zero-count cells remain visible in the count ledger.

## Outcome horizons

L13 focuses only on:

    H1
    H3
    H5

because L10/L11 showed early favorable excursion is the main behavior worth
explaining.

For each non-empty:

    era
    x relation
    x horizon

L13 reports clean matched:

    event-weighted return delta
    symbol-normalized return delta

    event-weighted MFE delta
    symbol-normalized MFE delta

plus:

    source target count
    clean pair count
    symbol count

Sign convention remains:

    TARGET - MATCHED CONTROL

Positive MFE means the candidate reached more favorable upside excursion than
its matched same-symbol, same-environment bearish control.

## Relation temporal consistency

For each:

    relation
    x horizon
    x metric
    x estimand

L13 counts:

    positive eras
    negative eras
    zero eras

and reports the strongest and weakest era.

Metrics:

    PAIRED_RETURN_DELTA_PCT
    PAIRED_MFE_DELTA_PCT

Estimands:

    EVENT_WEIGHTED
    SYMBOL_NORMALIZED

Expected row count:

    2 relations
    x 3 horizons
    x 2 metrics
    x 2 estimands
    = 24

This answers questions such as:

    Is HIGHER_CLASS MFE positive in 4/5 eras or 5/5?
    Is 2023-2026 the weakest HIGHER_CLASS era?

## Pooled prior-vs-latest comparison

L13 also pools:

    prior history through 2022

and compares it directly with:

    2023-2026

inside each relation.

For each:

    relation
    x horizon

it reports:

    prior source target count
    latest source target count

    prior/latest clean-pair count
    prior/latest symbol count

    prior/latest event-weighted return
    latest - prior return change

    prior/latest symbol-normalized return
    latest - prior return change

    prior/latest event-weighted MFE
    latest - prior MFE change

    prior/latest symbol-normalized MFE
    latest - prior MFE change

Expected row count:

    2 relations x 3 horizons = 6

This is the main table for deciding whether BOTH groups failed recently.

## Interaction contrast

L13 additionally reports a descriptive interaction contrast:

    SAME_CLASS latest-vs-prior change
    minus
    HIGHER_CLASS latest-vs-prior change

for every:

    horizon
    x metric
    x estimand

Expected row count:

    3 horizons
    x 2 metrics
    x 2 estimands
    = 12

Interpretation:

    negative contrast
        SAME_CLASS deteriorated more than HIGHER_CLASS

    positive contrast
        HIGHER_CLASS deteriorated more than SAME_CLASS

    near zero
        both relations changed similarly

This resembles a difference-in-differences contrast mathematically, but L13
does NOT treat it as a causal estimate.

There is no random assignment and no parallel-trends assumption.

It is a descriptive interaction diagnostic only.

## Source lineage

L13 fingerprints exact:

- L12 summary
- L12 context ledger
- L12 continuous-shift ledger
- L12 categorical-shift ledger
- L12 context-outcome ledger
- L8 matched pair-outcome ledger
- inherited frozen snapshot manifest hash

The candidate identities must match exactly between the L12 context ledger and
the L8 matched outcome ledger.

## Expected fixed top-level invariants

    requested_symbol_count              30

    alternate_target_count             305

    same_class_target_count            201
    higher_class_target_count          104

    prior_same_class_target_count      170
    prior_higher_class_target_count     93

    latest_same_class_target_count      31
    latest_higher_class_target_count    11

    era_count                            5
    relation_count                       2

    horizon_count                        3
    horizons                           1,3,5

    era_relation_count_row_count        10
    relation_consistency_row_count      24
    prior_latest_row_count               6
    interaction_contrast_row_count      12

    is_actionable                    false

Era-relation outcome row count is measured because an era/relation cell may
theoretically be empty.

## Outputs

    daily_no_supply_relation_era_summary.json
    daily_no_supply_relation_era_counts.csv
    daily_no_supply_relation_era_outcomes.csv
    daily_no_supply_relation_temporal_consistency.csv
    daily_no_supply_relation_prior_latest.csv
    daily_no_supply_relation_interaction_contrasts.csv

## Local validation

    python -m ruff check audit/daily_event_no_supply_relation_era_interaction.py scripts/audit_daily_event_no_supply_relation_era_interaction.py tests/test_daily_event_no_supply_relation_era_interaction.py

    python -m pytest -q tests/test_daily_event_no_supply_relation_era_interaction.py tests/test_daily_event_no_supply_alternate_context_profile.py

## Canonical run

    python scripts/audit_daily_event_no_supply_relation_era_interaction.py --context-dir reports\daily-events\no-supply-alternate-context-profile\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --matched-dir reports\daily-events\no-supply-matched-environment\milestone6_standard_india_large_cap_30_frozen_2026-09-18

## Interpretation order

Read the result in this order:

1. latest SAME_CLASS H1/H3/H5 MFE;
2. latest HIGHER_CLASS H1/H3/H5 MFE;
3. prior-vs-latest change inside each relation;
4. relation temporal consistency across all five eras;
5. interaction contrast.

### Outcome A — only SAME_CLASS fails

Example:

    SAME_CLASS latest H3 MFE      -0.25%
    HIGHER_CLASS latest H3 MFE    +0.60%

This would strengthen the case that SAME_CLASS is a genuine conditional
weakness.

The next step would still be matched/robustness validation before any production
rule.

### Outcome B — both relations fail

Example:

    SAME_CLASS latest H3 MFE      -0.25%
    HIGHER_CLASS latest H3 MFE    -0.20%

Then the recent breakdown is broader than the VolumeClass relation.

The missing state is likely elsewhere in ALTERNATE context or market regime.

### Outcome C — HIGHER_CLASS fails more

That would directly contradict the simple L12 hypothesis and prevent us from
promoting SAME_CLASS as the explanation.

## Safety

L13 changes no:

- NO_SUPPLY requirements;
- environment predicate;
- confirmation labels;
- confirmation gates;
- VolumeClass calculation;
- trend logic;
- evidence weights;
- scoring/ranking;
- DailyBehavior;
- qualification/actionability;
- API behavior;
- alerts/orders;
- production data loading.
