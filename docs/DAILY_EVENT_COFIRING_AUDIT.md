# M12 / L2 — Daily Event Frequency, Co-Firing & Gate Semantics Audit

## Purpose

L2 consumes the frozen L1 emission ledger and measures whether existing daily
event labels are distinct, nested, duplicated, broad, or tightly clustered.

L2 does not rerun market data and does not change any detector.

## Frozen input

Default input:

    reports/daily-events/inventory/<basket>/

Required L1 artifacts:

    daily_event_inventory_summary.json
    daily_event_emissions.csv

The source must be:

    audit_id = daily-event-inventory-point-in-time-v1
    failed_symbol_count = 0
    is_actionable = false

## Unique event identity

Frequency and co-firing use:

    symbol + bar_index + session + code

This intentionally removes same-bar duplicate emissions from overlap rates.

Raw emission counts remain separately visible so wiring duplication such as the
L1 ABSORPTION finding is not hidden.

## Frequency and concentration

For each emitted code L2 records:

- raw emission count;
- unique event count;
- duplicate extra count;
- rate over all evaluated L1 daily bars;
- number of symbols;
- most represented symbol;
- top-symbol share.

## Pairwise co-firing

Every pair of emitted codes receives:

- event counts;
- overlap count;
- percent of A accompanied by B;
- percent of B accompanied by A;
- Jaccard overlap;
- relationship.

Relationships:

    DISJOINT
    IDENTICAL_FIRING_SET
    A_STRICT_SUBSET_OF_B
    B_STRICT_SUBSET_OF_A
    PARTIAL_OVERLAP

These are descriptive structural relationships, not detector-quality scores.

## Cluster signatures

Every event bar is reduced to its sorted unique-code signature. L2 reports how
often each signature occurs and how many symbols exhibit it.

This shows whether named events mainly occur alone or as recurring multi-event
clusters.

## Detector confirmation-gate semantics

L2 also introspects the active detector source for collectors that call the
shared evaluate_detector() helper.

It records the mandatory requirement names and confirmation requirement names.

The current shared helper emits after mandatory requirements pass; it computes
confirmation_count(confirmations) but does not branch on that value. Therefore a
detector that supplies confirmations is reported as:

    CONFIRMATIONS_PRESENT_NON_GATING

This is an audit finding only. L2 does not change evaluate_detector().

## Outputs

    daily_event_cofiring_summary.json
    daily_event_frequencies.csv
    daily_event_pairwise.csv
    daily_event_cluster_signatures.csv
    daily_event_gate_semantics.csv

## Safety

L2 changes no:

- event detector;
- requirement;
- confirmation rule;
- evidence direction;
- evidence weight;
- DailyBehavior mapping;
- weekly qualification;
- scoring/ranking;
- DailyEntry trigger;
- API behavior;
- alert;
- order.

All outputs remain read-only and non-actionable.

## Next step

L2 should determine whether the next cut is a correctness fix for accidental
detector collapse/duplication, or L3 causal forward outcomes for event families
whose semantics are sufficiently distinct.
