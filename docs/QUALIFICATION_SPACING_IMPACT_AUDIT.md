# Qualification Spacing Counterfactual Audit

## Purpose

K16 isolates a production qualification-loop inconsistency discovered during the
K15 loop review.

The documented qualification constants are:

    MIN_QUALIFYING_EVENTS = 3
    MIN_EVENT_SPACING_BARS = 4

The pre-fix production selector walked backward from the newest event and
compared every older candidate to the newest event.

Example:

    events: 3, 5, 9

Current selector:

    9 - 5 = 4  -> accept
    9 - 3 = 6  -> accept
    => persistent using 3,5,9

Yet the accepted pair 3 -> 5 is only two bars apart.

K16 originally did not change production behavior. Its audit module now freezes
the pre-fix newest-anchor selector explicitly so the historical impact remains
reproducible after the production selector is corrected.

The strict comparator requires every older event to be at least four bars from
the last accepted event.

## Input

K16 reuses the validated K14 frozen progression artifacts:

    progression_directionality_events.csv
    progression_directionality_symbols.csv

No market-data download or scanner replay is required.

## Output

For every progression event, the ledger records:

- symbol;
- campaign id;
- event bar/week/direction;
- spacing from the prior event;
- current production qualification;
- current selected event bars;
- strict pairwise qualification;
- strict selected event bars;
- divergence flag and kind.

The symbol summary reports affected campaigns and first divergence.

## CLI

Run:

    python scripts/audit_qualification_spacing_impact.py

Outputs:

    reports/daily-behavior-sequences/qualification-spacing/milestone6_standard_india_large_cap_30/qualification_spacing_impact_summary.json
    reports/daily-behavior-sequences/qualification-spacing/milestone6_standard_india_large_cap_30/qualification_spacing_impact_events.csv
    reports/daily-behavior-sequences/qualification-spacing/milestone6_standard_india_large_cap_30/qualification_spacing_impact_symbols.csv

## Safety

Read-only and explicitly non-actionable.

K16 does not modify PatternQualificationEngine, ScannerTransitionEngine,
candidate actionability, WeeklySetup materialization, daily coordination,
alerts, execution, or orders.
