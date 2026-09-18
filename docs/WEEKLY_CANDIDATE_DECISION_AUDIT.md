# Production Weekly Candidate Decision Audit

## Purpose

K11 audits all production weekly ScannerCandidate outputs before WeeklySetup
materialization.

The first real LT.NS authority audit showed:

    243 production weekly candidates
    37 materialized WeeklySetup rows
    37 bearish / 0 bullish setups
    463 bearish / 0 bullish daily assignments

K11 localizes the asymmetry one boundary earlier.

## What is recorded

For every historical production candidate:

- week and bar index;
- final qualification enum;
- whether qualification evidence remains actionable;
- final candidate actionability;
- whether the existing materializer creates a WeeklySetup;
- materialized direction;
- professional confidence;
- net strength / net pressure;
- scoring bar and scoring-evidence age;
- fallback-evidence usage;
- anomaly gate;
- exact final reason;
- qualifying evidence codes;
- scoring evidence codes.

The summary separately counts:

- all candidates by qualification;
- actionable candidates by qualification;
- materialized setups by direction;
- persistent-bullish final reasons;
- persistent-bearish final reasons;
- anomaly and fallback-evidence counts.

## Interpretation

If LT contains persistent_bullish candidates but zero actionable bullish
candidates, the ledger will show which existing final scanner reasons blocked
them.

If LT contains zero persistent_bullish candidates at all, the one-sided result
originates earlier in structural qualification rather than actionability or the
WeeklySetup materializer.

K11 reports existing behavior only. It does not alter thresholds, qualification,
VSA confirmation, actionability, ranking, or setup materialization.

## CLI

Run:

    python scripts/audit_weekly_candidate_decisions.py LT.NS --now 2026-09-18T16:00:00+05:30

Outputs:

    reports/daily-behavior-sequences/weekly-candidates/LT_NS/weekly_candidate_decision_summary.json
    reports/daily-behavior-sequences/weekly-candidates/LT_NS/weekly_candidate_decision_ledger.csv

All outputs remain research-only and non-actionable.
