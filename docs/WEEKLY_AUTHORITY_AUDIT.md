# Production Weekly Authority Audit

## Purpose

K10 explains how production weekly qualification becomes daily weekly-direction
authority without modifying either path.

It distinguishes:

    production weekly setups created
    !=
    setup selected for each daily session

This is required before broadening the real M11 study because the first LT.NS
frozen case contains 37 production weekly setups but all 463 daily assignments
are bearish.

## Authority chain

K10 reuses:

    K8 production weekly derivation
    → WeeklySetup history
    → K6 causal weekly-direction assignments

For every materialized WeeklySetup the ledger records:

- setup id;
- signal week;
- direction;
- qualification;
- lifecycle status;
- weekly completion session;
- first daily session where the setup is causally available;
- number of daily sessions where the coordinator actually selected it;
- first selected daily session;
- last selected daily session.

The summary separately reports setup direction counts and daily assignment
direction counts.

## Interpretation

If LT has zero bullish WeeklySetup rows, the asymmetry originates in the
production weekly candidate/materializer input.

If bullish WeeklySetup rows exist but receive zero or very few selected daily
sessions, the asymmetry is in the sequence/timing of coordinator authority.

K10 does not decide that either result is wrong. It makes the source explicit
for manual evidence review.

## CLI

Run:

    python scripts/audit_weekly_setup_authority.py LT.NS --now 2026-09-18T16:00:00+05:30

Outputs:

    reports/daily-behavior-sequences/weekly-authority/LT_NS/weekly_authority_summary.json
    reports/daily-behavior-sequences/weekly-authority/LT_NS/weekly_setup_authority_ledger.csv

All outputs are research-only and non-actionable.
