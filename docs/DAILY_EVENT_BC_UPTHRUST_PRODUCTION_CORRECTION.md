# M12 — BUYING_CLIMAX / UPTHRUST Production Correction

## Status

Production correction merged.

PR #348 merged the promoted M12 BC/UPTHRUST semantic contracts into `main`.

Research is closed. The detector definitions are not being tuned further.
The frozen-snapshot replay, exact candidate parity, non-target drift review,
Spring quality dependency review, and contribution-impact review all passed
before merge.

## Why production changes now

The canonical frozen study established that the old production contracts were:

    BUYING_CLIMAX
        Buying Campaign
        Bullish Bar
        Very High Volume
        Above Average Spread

    UPTHRUST
        Buying Campaign
        Bullish Bar
        Very High Volume
        Above Average Spread

Because confirmations do not gate emission, both codes fired on exactly the same:

    4,497 events

The later semantic replay and final validation promoted two distinct contracts.

Final L18 status:

    BC_EXHAUSTION_CANDIDATE
        PROMOTE

    UT_STRUCTURAL_REJECTION_CANDIDATE
        PROMOTE

    local previous-high UPTHRUST
        REJECT

    further definition search
        STOP

## Production BUYING_CLIMAX contract

BUYING_CLIMAX retains the already-validated effort/background core:

    Buying Campaign
    Bullish Bar
    Very High Volume
    Above Average Spread

and adds the promoted mandatory semantic gate:

    Non-Strong High Acceptance

Exact implementation:

    close_position NOT IN
        UPPER
        ON_HIGH

Therefore accepted close buckets are:

    MIDDLE
    LOWER
    ON_LOW

Semantic interpretation:

    climactic buying effort
    without strong acceptance at the high

The PR does not introduce a new close-ratio threshold.

Existing confirmations remain descriptive:

    Wide Spread
    Weak Close
    Increasing Volume

They remain non-gating under the current shared detector helper.

## Production UPTHRUST contract

UPTHRUST no longer inherits the old BUYING_CLIMAX mandatory contract.

The promoted identity is:

    current high
        >
    latest causally confirmed structural swing-high price

    AND

    current close
        <=
    that structural swing-high price

Mandatory requirements are therefore:

    Confirmed Structural High
    Probe Above Structural High
    Failed Acceptance Above Structural High

## Structural causality

collect_supply can inspect multiple bars while sharing one BackgroundContext
structural-swing tuple.

The UPTHRUST helper therefore must not simply use the last structural swing.

For each bar it explicitly selects the latest structural HIGH satisfying:

    swing.type == HIGH
    confirmation_index <= current bar_index
    swing bar_index < current bar_index

This prevents:

- future-confirmed structural highs from leaking backward;
- the current bar from becoming its own resistance reference.

A structural high confirmed on the current bar is allowed when its pivot bar is
earlier.

This matches the frozen L17 causal replay contract.

## UPTHRUST descriptors

The old mandatory requirements:

    Buying Campaign
    Bullish Bar
    Very High Volume
    Above Average Spread

are removed from event identity.

L17 showed that structural rejection naturally occurs across a wider range of:

    bar direction
    volume class
    spread class
    close position

The production collector retains these descriptive confirmations:

    Weak Close
    Very High Volume
    Above Average Spread

They are not mandatory.

## Evidence profiles

Evidence direction remains unchanged:

    BUYING_CLIMAX -> BEARISH
    UPTHRUST      -> BEARISH

Both remain primary VSA evidence codes.

Existing dynamic weight calculators remain unchanged in this PR.

Only the emission contracts change.

Descriptions are updated to match the promoted semantics.

## DailyBehavior boundary

This PR intentionally does NOT modify daily_behavior.py.

Current bearish mapping remains:

    BUYING_CLIMAX
        -> REJECTION_OF_OPPOSING_MOVE

    UPTHRUST
        -> REJECTION_OF_OPPOSING_MOVE

L18 proved that this behavior layer still collapses two now-distinct detector
roles.

That is a later DailyBehavior recalibration task.

It must not be silently bundled into the detector production correction.

## Expected frozen production identities

The promoted L17/L18 identities are fixed before production replay.

Expected post-change counts:

    BUYING_CLIMAX
        887

    UPTHRUST
        10,526

    same-bar overlap
        129

Expected relationship:

    PARTIAL_OVERLAP

These are semantic parity gates, not performance targets.

If actual production replay differs from these identities, do not merge.

## Non-target safety gate

Only BUYING_CLIMAX and UPTHRUST event identities are allowed to change.

The production-impact audit compares all other event identities across the
exact same frozen snapshot.

Required:

    non_target_identity_drift_count = 0
    unexpected_non_target_attribute_drift_count = 0
    non_target_emission_drift_count = 0

One existing downstream dependency is explicitly recognized:

    SPRING quality

Spring already reduces quality from 1.0 to 0.5 when a same-bar
BUYING_CLIMAX or UPTHRUST conflict exists.

Because this PR intentionally changes BC/UT identity, an unchanged Spring event
may legitimately change quality when that same-bar conflict state changes.

The audit permits that change only when:

    Spring event identity is unchanged
    all non-quality Spring fields are unchanged
    BC/UT conflict presence changed on the same bar
    before quality exactly matches the old conflict state
    after quality exactly matches the new conflict state

Such rows are reported as:

    spring_conflict_quality_change_count

Any other non-target identity or attribute change fails the audit.

This protects the rest of the daily evidence vocabulary without incorrectly
treating a documented downstream dependency as unrelated drift.

## Scoring impact

Both codes remain members of PRIMARY_VSA_CODES.

The active EvidenceAggregator groups evidence by:

    bar_index
    direction

and anchors a primary event group by the maximum:

    weight * strength

rather than independently summing every primary label.

Therefore the old identical BC+UT firing did not simply double the same-bar
primary contribution.

However the new semantics:

- remove many old BC/UT emissions;
- add structural UPTHRUST emissions on previously different bars;
- change which primary weight anchors some bearish event groups.

The impact audit therefore recomputes the active
EvidenceAggregator event-contribution contract from the before and after
emission ledgers.

It reports:

    changed event-direction groups
    increased groups
    decreased groups

    total before event contribution
    total after event contribution
    total delta

    mean absolute changed-group delta
    maximum absolute changed-group delta

and per-symbol changed contribution summaries.

Important:

    this is an event-contribution impact audit

not:

    a scanner trade score
    a ranking result
    a recommendation
    actionability

## Local code validation

Run:

    python -m ruff check evidence/supply.py evidence/profiles.py audit/daily_event_bc_upthrust_production_impact.py scripts/audit_daily_event_bc_upthrust_production_impact.py tests/test_bc_upthrust_production_semantics.py tests/test_daily_event_bc_upthrust_production_impact.py tests/test_campaign_snapshot_collectors.py tests/test_daily_event_confirmation_semantics.py tests/test_daily_event_bc_upthrust_identity_separation.py tests/test_daily_event_detector_correction_design.py

Then:

    python -m pytest -q tests/test_bc_upthrust_production_semantics.py tests/test_daily_event_bc_upthrust_production_impact.py tests/test_campaign_snapshot_collectors.py tests/test_daily_event_confirmation_semantics.py tests/test_daily_event_bc_upthrust_identity_separation.py tests/test_daily_event_detector_correction_design.py tests/test_daily_event_bc_upthrust_final_validation.py tests/test_daily_behavior_evidence.py

## Frozen post-change inventory replay

Do NOT overwrite the canonical pre-change inventory.

Use a dedicated output directory:

    reports\daily-events\inventory\milestone6_standard_india_large_cap_30_frozen_2026-09-18_bc-ut-production-fix

Run:

    python scripts/audit_daily_event_inventory.py --input-snapshot-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30\2026-09-18 --now 2026-09-18T16:00:00+05:30 --workers 4 --output-dir reports\daily-events\inventory\milestone6_standard_india_large_cap_30_frozen_2026-09-18_bc-ut-production-fix

Required inventory gates:

    requested_symbol_count
        30

    succeeded_symbol_count
        30

    failed_symbol_count
        0

    evaluated_bar_count
        198382

## Production impact audit

Before directory:

    reports\daily-events\inventory\milestone6_standard_india_large_cap_30_frozen_2026-09-18

After directory:

    reports\daily-events\inventory\milestone6_standard_india_large_cap_30_frozen_2026-09-18_bc-ut-production-fix

Semantic authority:

    reports\daily-events\bc-upthrust-semantic-replay\milestone6_standard_india_large_cap_30\2026-09-18

Run:

    python scripts/audit_daily_event_bc_upthrust_production_impact.py --before-dir reports\daily-events\inventory\milestone6_standard_india_large_cap_30_frozen_2026-09-18 --after-dir reports\daily-events\inventory\milestone6_standard_india_large_cap_30_frozen_2026-09-18_bc-ut-production-fix --semantic-dir reports\daily-events\bc-upthrust-semantic-replay\milestone6_standard_india_large_cap_30\2026-09-18 --output-dir reports\daily-events\bc-upthrust-production-impact\2026-09-18

Hard impact gates:

    before_bc_count
        4497

    before_ut_count
        4497

    before_overlap_count
        4497

    after_bc_count
        887

    after_ut_count
        10526

    after_overlap_count
        129

    expected_bc_count
        887

    expected_ut_count
        10526

    expected_overlap_count
        129

    bc_candidate_identity_mismatch_count
        0

    ut_candidate_identity_mismatch_count
        0

    non_target_identity_drift_count
        0

    unexpected_non_target_attribute_drift_count
        0

    non_target_emission_drift_count
        0

Spring conflict-quality recalculations are reported separately and must be
reviewed. They are allowed only when the audit proves that they are exactly
implied by the existing same-bar BC/UPTHRUST conflict rule.

Contribution-delta counts and magnitudes are findings.

They are not pre-optimized thresholds.

## Merge rule

Merge only when:

1. focused Ruff passes;
2. focused pytest passes;
3. frozen post-change inventory succeeds for all 30 symbols;
4. production BC identities exactly reproduce the frozen promoted BC candidate;
5. production UT identities exactly reproduce the frozen promoted UT candidate;
6. non-target event identity drift is zero;
7. unexpected non-target attribute drift is zero;
8. any Spring quality changes are fully explained by the existing same-bar
   BC/UPTHRUST conflict dependency;
9. contribution impact is reviewed and shows no unexpected implementation
   anomaly.

## After merge

Do not reopen BC/UPTHRUST definition research.

Next work should return to the remaining broader M12 detector-correctness backlog.

DailyBehavior distinction can be handled later during the planned behavior
recalibration phase.

## Safety

This production correction changes detector emissions and therefore can change
professional evidence contribution.

It does not directly change:

- detector weights;
- evidence direction;
- primary/supporting classification;
- DailyBehavior mappings;
- weekly qualification;
- weekly thesis authority;
- entry/actionability rules;
- alerts;
- orders;
- market-data loading.
