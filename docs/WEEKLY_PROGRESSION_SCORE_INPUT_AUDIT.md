# Production Weekly Progression Score Input Audit

## Purpose

K13 decomposes the exact structural-swing score windows that produced K12's
weekly progression events.

K12 showed LT.NS emitted:

    1 improving event
    6 weakening events

The single improving event was immediately followed by a bearish event, while
three spaced bearish events established persistent-bearish qualification.

K13 asks why the professional progression differences are predominantly
negative.

## Score chain

The production score chain is:

    professional overall
    ├── structural score (80%)
    │   ├── price percentile
    │   ├── structural-size percentile
    │   ├── duration percentile
    │   ├── volume percentile
    │   └── spread percentile
    └── smart-money score (20%)

Progression compares recency-weighted averages of recent versus older structural
swing professional scores.

## Outputs

K13 writes:

- one unique structural-swing score ledger;
- one progression-window ledger;
- one compact summary JSON.

For every progression event, the window ledger records:

- older and recent confirmation ranges;
- window size;
- reported progression difference;
- independently reconstructed progression difference;
- exact reconstruction match flag;
- older/recent professional weighted averages;
- professional delta;
- structural-overall delta;
- smart-money-overall delta;
- price, structural-size, duration, volume, and spread score deltas;
- stopping-volume and climactic-volume Smart Money deltas.

The swing ledger retains the exact score components and history-snapshot inputs
for every unique production structural swing.

## CLI

Run:

    python scripts/audit_weekly_progression_scores.py LT.NS --now 2026-09-18T16:00:00+05:30

Outputs:

    reports/daily-behavior-sequences/weekly-progression-scores/LT_NS/weekly_progression_score_input_summary.json
    reports/daily-behavior-sequences/weekly-progression-scores/LT_NS/weekly_structural_swing_score_ledger.csv
    reports/daily-behavior-sequences/weekly-progression-scores/LT_NS/weekly_progression_score_window_ledger.csv

## Safety

Read-only and non-actionable.

K13 does not alter structural swing discovery, structural scoring, Smart Money
scoring, professional weights, progression windows, progression thresholds,
qualification, scanner actionability, WeeklySetup materialization, coordinator
selection, alerts, execution, or orders.
