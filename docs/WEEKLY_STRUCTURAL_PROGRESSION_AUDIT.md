# Production Weekly Structural Progression Audit

## Purpose

K12 audits the exact structural-progression event stream feeding
PatternQualificationEngine.

K11 established that LT.NS has:

    243 weekly candidates
    136 unqualified
    107 persistent-bearish
    0 persistent-bullish

The candidate history has only two qualification regimes: unqualified through
2024-08-26, then persistent-bearish from 2024-09-02 through the study cutoff.

K12 determines whether:

1. STRUCTURAL_PROGRESSION_IMPROVING was never emitted, or
2. improving events were emitted but their timing/spacing/opposing-event state
   never produced persistent-bullish qualification.

## Event ledger

For every emitted structural-progression event, K12 records:

- event bar/week/code/direction/strength;
- professional progression difference;
- structural swing count;
- latest confirmed structural swing type, label, pivot, confirmation bar, week,
  grade, and professional overall score;
- previous progression event and spacing;
- previous same-direction event and spacing;
- whether same-direction spacing meets the existing qualification minimum;
- qualification state immediately after the event;
- whether the event is one of the candidate's selected qualifying events.

The event source is the existing production ScannerCandidate target-bar evidence.
K12 does not rerun a substitute progression detector.

## CLI

Run:

    python scripts/audit_weekly_structural_progression.py LT.NS --now 2026-09-18T16:00:00+05:30

Outputs:

    reports/daily-behavior-sequences/weekly-progression/LT_NS/weekly_structural_progression_summary.json
    reports/daily-behavior-sequences/weekly-progression/LT_NS/weekly_structural_progression_ledger.csv

## Safety

Read-only and non-actionable.

K12 does not change swing detection, structural scoring, progression thresholds,
PatternQualificationEngine, VSA confirmation, candidate actionability, ranking,
WeeklySetup materialization, coordinator selection, alerts, execution, or orders.
