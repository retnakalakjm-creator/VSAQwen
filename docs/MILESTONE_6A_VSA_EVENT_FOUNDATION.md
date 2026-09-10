# Milestone 6A: VSA Event Foundation

Milestone 6A freezes the backend VSA event-foundation work completed after the original Milestone 6 documentation checkpoint.

The goal of this phase was not to activate more detectors. The goal was to make the audit foundation reliable enough to understand when a VSA event should be trusted, invalidated, conflicted, superseded, or deferred for chart review.

Project rule:

```text
foundation first, visualization second
```

## Scope of 6A

Milestone 6A covers PR #85 through PR #95.

It includes:

- VSA event causality diagnostics;
- mixed-event causality labels;
- grouped mixed-event cluster review;
- mixed-cluster grading and action proposals;
- lifecycle transition proposals;
- lifecycle proposal casebook export;
- the first production-safe lifecycle conflict behavior;
- frontend display of pending supersession;
- a deferred visual replay roadmap;
- expanded audit baskets;
- Tata Motors demerger symbol maintenance.

It does not include broad production activation of Stopping Volume, Spring/Shakeout, Absorption, Effort-vs-Result, or High Volume Reversal.

## Completed PRs

### PR #85: VSA event causality diagnostics

Added audit diagnostics to inspect whether candidate VSA events are followed by confirming, conflicting, or insufficient later evidence.

This shifted the workflow away from single-bar detector inspection and toward event outcome review.

### PR #86: Mixed-event causality labels

Added labels for cases where later evidence contains both same-side follow-through and opposing evidence.

This made mixed outcomes visible instead of treating them as clean pass/fail cases.

### PR #87: Grouped mixed-event cluster review

Grouped nearby mixed-event rows by symbol and replay window.

This established that many noisy cases should be reviewed as clusters rather than as independent candidate rows.

### PR #88: Mixed-cluster grading and action proposals

Added grading and recommended action categories for mixed clusters.

This helped separate cleaner lifecycle-review cases from detector-gate noise and broad false-positive risks.

### PR #89: Mixed-cluster lifecycle transition proposals

Converted graded mixed clusters into audit-only lifecycle transition proposals.

This created a safe bridge from audit findings to possible lifecycle behavior without changing production detector rules.

### PR #90: Lifecycle proposal casebook export

Added casebook export for lifecycle proposals.

This gave the project a repeatable artifact for reviewing high-value cases before touching scanner behavior.

### PR #91: Bearish lifecycle conflict pending supersession

Added the first production-safe lifecycle behavior from the audit casebook.

Fresh demand or reversal evidence against an active persistent-bearish context now marks the lifecycle as conflicted and pending supersession instead of flipping bullish or invalidating the bearish context too aggressively.

Important behavior:

```text
persistent_bearish + fresh demand/reversal evidence
  -> conflicted
  -> pending_supersession = true
```

This uses existing production VSA evidence only. Audit-only candidates remain ignored.

### PR #92: Display pending supersession in VSA Story

Exposed the PR #91 pending-supersession lifecycle state in the frontend VSA Story panel.

This made the backend lifecycle distinction visible without adding detector activation or replay behavior.

### PR #93: Future point-in-time replay milestone

Documented a future TradingView-style point-in-time replay and visual casebook milestone.

This intentionally deferred visualization until the backend audit foundation became stronger.

### PR #94: Expanded VSA audit baskets

Added repeatable audit baskets:

- `milestone6_standard_india_large_cap_30`
- `milestone6_expanded_india_large_mid_60`
- `milestone6_midcap_focus_30`

The expanded basket exists to test consistency and false-positive behavior before any new backend event-family activation.

### PR #95: Tata Motors demerger symbol maintenance

Updated repeatable audit baskets after the Tata Motors symbol changes.

Basket changes:

```text
TATAMOTORS.NS -> TMPV.NS
```

The expanded basket also includes:

```text
TMCV.NS
```

To keep the expanded basket exactly 60 symbols, `IOC.NS` was removed from the expanded additional-symbol list.

This was basket maintenance only. It did not change scanner logic, detectors, scoring, ranking, replay, API behavior, frontend behavior, persistence, or market-data loading.

## Main 6A conclusion

Milestone 6A showed that the next problem is not simply detector activation.

The core issue is lifecycle handling:

- when bearish context remains valid;
- when demand/reversal evidence should create conflict;
- when conflict should become pending supersession;
- when a prior qualification should expire or be invalidated;
- when mixed event clusters should block detector activation;
- when broader-basket evidence is too noisy for production behavior.

The expanded audit showed meaningful signal, but also enough mixed-event and detector-gate noise that broad detector activation is not justified yet.

## Important audit findings preserved from 6A

The LT.NS case remains the key lifecycle example.

In March 2026, LT.NS showed persistent bearish qualification challenged by demand/reversal evidence. The correct production-safe behavior was not a bullish flip. It was a conflicted bearish lifecycle state pending supersession.

The expanded audit also produced other lifecycle-review examples, including DRREDDY.NS, GRASIM.NS, AMBUJACEM.NS, GODREJCP.NS, and BRITANNIA.NS.

These cases should be used for chart review and future lifecycle-rule validation.

## What 6A deliberately did not do

Milestone 6A did not:

- activate Effort-vs-Result broadly;
- activate Absorption broadly;
- activate High Volume Reversal broadly;
- add a TradingView-style replay UI;
- change scanner scoring or ranking;
- treat audit-only diagnostics as production events;
- bypass chart review for noisy mixed clusters.

## Next phase

The next backend event-foundation phase should start from the 6A conclusion and focus on:

```text
Stopping Volume -> Spring / Shakeout recovery sequence
```

Before implementation, the project should rerun the expanded basket after PR #95 and compare whether `TMPV.NS` or `TMCV.NS` adds new lifecycle or detector-gate clusters.

A later documentation split can use:

```text
MILESTONE_6B_STOPPING_VOLUME_SPRING_SHAKEOUT.md
MILESTONE_6C_VISUAL_REPLAY_CASEBOOK.md
```

## Guardrails for future audit/debug scripts

Before committing any future audit or debug script, check:

- loop structure;
- data-loading and replay count;
- production-path consistency;
- imports;
- obvious object/API mismatches;
- optimization opportunities.

This prevents long audit runs from exposing issues that could have been caught before committing.

## Current status

Milestone 6A is complete after PR #95.

The next recommended step is not detector activation. The next step is to rerun the expanded basket with the updated Tata Motors symbols and compare the output against the pre-PR #95 expanded audit artifacts.
