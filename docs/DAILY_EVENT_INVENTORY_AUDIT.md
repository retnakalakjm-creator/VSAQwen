# M12 / L1 — Daily Event Inventory & Point-in-Time Audit

## Purpose

L1 starts detector-level daily-event validation.

It does not add a new detector, change an existing detector, change scoring, or
promote any daily behavior to production actionability.

The goal is to answer a more basic question first:

    What daily event vocabulary exists today,
    what can the active EvidenceEngine actually emit,
    what is mapped into DailyBehavior,
    and what is observed point-in-time on real daily bars?

## Static inventory boundaries

For every EvidenceCode, L1 records:

- enum-defined;
- registered in evidence.profiles.EVIDENCE_REGISTRY;
- registered in the legacy evidence.evidence_registry.EVIDENCE_LIBRARY;
- reachable through the active EvidenceEngine.collect() collector path;
- collector source(s);
- mapped bullish DailyBehavior dimensions;
- mapped bearish DailyBehavior dimensions;
- declared evidence direction where the current registries define one;
- whether that declared direction can actually pass DailyBehavior's
  bullish/bearish aligned-direction filter.

This intentionally distinguishes definitions from runtime reachability.

A code may therefore be:

    defined
    registered
    behavior-mapped
    actively collected
    actually emitted

and those states are not assumed to be equivalent.

## Point-in-time runtime audit

L1 reuses K5's existing prefix-only daily evidence producer:

    raw completed daily history
    -> prefix ending at target D
    -> MetricsEngine
    -> SwingEngine
    -> StructureFilter
    -> TrendAnalyzer
    -> EvidenceEngine
    -> retain evidence whose bar_index == target D

The future suffix is never passed to the evaluator.

For every emitted event, L1 records symbol, target bar/session, code, category,
direction, strength, weight, quality, and test/recovery provenance.

## Duplicate-emission audit

L1 also groups emissions by:

    symbol + target bar + session + code

and writes any group with count > 1.

This is important because the current active path can reach ABSORPTION through
both collect_demand() and collect_effort(). L1 measures the runtime consequence;
it does not fix or deduplicate it in this PR.

L1 also exposes behavior-map direction mismatches. For example, a code may be
listed in a bullish or bearish DailyBehavior dimension while its declared
Evidence direction is neutral or opposite. Because evaluate_daily_behavior()
filters evidence by weekly-aligned EvidenceDirection before applying code maps,
such a mapping cannot currently contribute to that behavior dimension.

## Outputs

    daily_event_inventory_summary.json
    daily_event_inventory.csv
    daily_event_emissions.csv
    daily_event_duplicates.csv
    daily_event_failures.csv

## Status labels

Inventory rows use descriptive labels only:

    EMITTED_POINT_IN_TIME
    ACTIVE_NOT_OBSERVED
    BEHAVIOR_MAPPED_BUT_INACTIVE
    REGISTERED_BUT_INACTIVE
    DEFINED_BUT_INACTIVE

These are audit states, not quality judgments.

## Safety

L1 is read-only and non-actionable.

It changes no:

- Evidence detector rule;
- evidence weight;
- scanner qualification;
- scoring/ranking;
- WeeklySetup;
- DailyEntry trigger;
- alert;
- order;
- production API behavior.

## Next step

After broad-basket L1 evidence is reviewed, L2 should measure event frequency,
symbol concentration, event clustering, dead/rare events, and duplicate-emission
patterns before any event-outcome audit or detector change.
