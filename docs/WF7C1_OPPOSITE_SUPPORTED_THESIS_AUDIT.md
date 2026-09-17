# WF7C1 — Opposite Supported Thesis Decomposition Audit

## Purpose

WF7B showed that `OPPOSITE_SUPPORTED_THESIS` is the only contradiction class still worth deeper study, but its out-of-sample effect weakened with horizon and varied materially by symbol. WF7C1 therefore remains research-only and asks a narrower question:

> When a legacy-actionable weekly setup is opposed by a supported shadow thesis, does that relationship remain adverse after episode normalization, direction/regime stratification, symbol balancing, matched controls, out-of-sample separation, and a frozen WF7C0 input fingerprint contract?

WF7C1 does **not** change qualification, actionability, scoring, ranking, `WeeklySetup`, daily entry, alerts, execution, or orders.

## Input reproducibility gate

WF7C1 starts through `run_reproducible_weekly_foundation_study(...)`, fingerprints the exact completed-week OHLCV frame consumed by the historical study, and compares it with the caller-supplied WF7C0 baseline manifest.

If any symbol is missing or any fingerprint field changes — version, row count, first week, last week, SHA-256, or canonical columns — the study stops with an input-mismatch error. This prevents market-data revisions from being silently interpreted as logic changes.

## Sample unit

WF7C1 uses **WF7B episode starts only**. Consecutive weeks in the same reason episode are not counted as independent observations.

The treatment cohort is only:

- `OPPOSITE_SUPPORTED_THESIS`

Reference/control candidates are episode starts classified as:

- `SAME_DIRECTION_SUPPORTED`
- `SHADOW_SUPPORT_MISSING`

`CAMPAIGN_CHALLENGED` and `STRUCTURAL_INVALIDATION` are not controls.

## Regime decomposition

Each episode start is enriched from the same point-in-time weekly audit with:

- legacy direction
- trend direction
- trend state
- structural pattern
- in-sample / out-of-sample partition

The report emits treatment summaries across these dimensions for 5/10/15-week outcomes.

## Symbol-balanced aggregation

Ordinary pooled means can be dominated by symbols that contribute many episodes. WF7C1 therefore also computes equal-weight symbol means: first calculate the outcome mean within each contributing symbol, then average those symbol means.

This is diagnostic only. No weighting rule is promoted into production.

## Matched-control audit

Each treatment attempts a one-to-one exact match on:

- symbol
- partition
- legacy direction
- trend direction
- trend state
- structural pattern

Among eligible unused controls, the nearest bar index is selected, with deterministic tie-breaking. Matching is retrospective historical research; it never feeds a live or replay decision.

Matched summaries expose treatment/control close return, MFE and MAE, paired deltas, median paired close delta, and a symbol-balanced paired close delta. Unmatched treatments remain visible rather than being discarded silently.

## Interpretation gate

WF7C1 is evidence for review, not an automatic promotion engine. A production change should not follow merely because a pooled mean is negative. Review must consider at least:

- out-of-sample sign and magnitude
- episode-start sample size
- bullish versus bearish legacy direction
- regime stability
- equal-weight symbol results
- matched-control separation
- unmatched-treatment rate
- leave-one-symbol / symbol heterogeneity using exported observations and pair records
- complete-outcome counts at each horizon

If these views disagree materially, `OPPOSITE_SUPPORTED_THESIS` remains audit context only.

## Expected artifacts

The runner exports:

- `wf7c1_opposite_supported_summary.json`
- `wf7c1_opposite_supported_observations.csv`
- `wf7c1_opposite_supported_regime_summaries.csv`
- `wf7c1_opposite_supported_symbol_balanced.csv`
- `wf7c1_opposite_supported_matched_pairs.csv`
- `wf7c1_opposite_supported_matched_summaries.csv`
- `wf7c1_opposite_supported_unmatched.csv`
- `wf7c1_input_fingerprints.csv`

Every report remains `is_actionable = false`.

## Safety boundary

WF7C1 introduces no detector, threshold, evidence weight, score, qualification rule, contradiction veto, ranking policy, setup lifecycle mutation, daily trigger, execution behavior, alert, or order behavior.
