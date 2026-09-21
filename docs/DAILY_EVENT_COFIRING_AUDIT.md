# M12 / L2 — Daily Event Frequency, Co-Firing & Gate Semantics Audit

## Purpose

L2 consumes the frozen L1 emission ledger and measures whether existing daily
event labels are distinct, nested, duplicated, broad, or tightly clustered.

L2 does not rerun market data and does not change any detector.

## Frozen input

For the canonical M12 rerun, pass the regenerated frozen L1 directory explicitly:

    reports/daily-events/inventory/milestone6_standard_india_large_cap_30_frozen_2026-09-18/

Required L1 artifacts:

    daily_event_inventory_summary.json
    daily_event_emissions.csv

The source must be:

    audit_id = daily-event-inventory-point-in-time-v1
    requested_symbol_count = succeeded_symbol_count
    failed_symbol_count = 0
    is_actionable = false
    input_provenance.source = FROZEN_DAILY_INPUT_SNAPSHOT
    input_provenance.snapshot_audit_id = daily-audit-input-snapshot-v1
    input_provenance.snapshot_period = max

L2 rejects the old heterogeneous-cache L1 ledger because it does not carry
frozen-snapshot provenance.

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

## Source lineage

L2 records the exact L1 lineage in its summary:

- snapshot audit id;
- snapshot manifest SHA-256;
- snapshot basket;
- snapshot period and cutoff;
- SHA-256 of the consumed L1 summary JSON;
- SHA-256 of the consumed L1 emissions CSV.

This lets downstream L3 prove that it is using the same regenerated canonical
L1/L2 chain.

## Outputs

When an explicit frozen L1 input directory is supplied, the default L2 output
directory uses the same source-directory name under:

    reports/daily-events/cofiring/

Files:

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


## Canonical frozen L2 command

```powershell
python scripts/audit_daily_event_cofiring.py --input-dir reports\daily-events\inventory\milestone6_standard_india_large_cap_30_frozen_2026-09-18
```

The regenerated L2 output defaults to:

    reports\daily-events\cofiring\milestone6_standard_india_large_cap_30_frozen_2026-09-18


## Current M12 handoff after NO_SUPPLY closure

The NO_SUPPLY branch of the M12 detector investigation is now closed for the
current audit cycle.

Authoritative closure record:

    docs/DAILY_EVENT_NO_SUPPLY_RESEARCH_VERDICT.md

That investigation concluded:

- no production NO_SUPPLY correction is currently justified;
- WEAK_RESULT_ONLY remains research-only;
- further detector-specific subgroup slicing would create increasing
  data-mining risk.

The next M12 correctness priority therefore returns to the strongest unresolved
L2 structural finding:

    BUYING_CLIMAX
    vs
    UPTHRUST

Canonical frozen L2 established:

    BUYING_CLIMAX unique events     4,497
    UPTHRUST unique events          4,497
    overlap                         4,497
    relationship                    IDENTICAL_FIRING_SET

The next audit should determine why two named production detectors have the
same canonical daily firing set before any further NO_SUPPLY research is
started.
