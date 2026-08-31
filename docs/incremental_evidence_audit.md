# Incremental Evidence / VSA Audit

## Status

Audit-only. No production evidence behavior is changed by this document.

## Finding

The active EvidenceEngine does **not** currently have a clean, independently defined minimal persisted state.

The correct design boundary is different:

```text
persisted structural/trend state
        +
minimum metric replay window
        ↓
EvidenceEngine
```

A separate `EvidenceState` should not be invented until the current evidence detectors are refactored around explicit causal inputs.

## Active Evidence Dependencies

### Supply

`evidence/supply.py` evaluates each bar in `BackgroundContext.bars`.

Most active supply detectors use:

- current bar
- previous bar
- semantic classifications already present in metrics
- buying-campaign context

The campaign logic uses a recent bar sequence rather than arbitrary distant history.

### Demand

`evidence/demand.py` uses:

- current bar
- previous bar
- campaign context
- trend context
- point-in-time metric history for SHAKEOUT

`STOPPING_VOLUME`, `SELLING_CLIMAX`, `INCREASING_DEMAND`, `TEST`, and `NO_SUPPLY` are primarily current/previous-bar detectors plus campaign/trend context.

### Campaign context

`evidence/campaign.py` currently uses the recent `ctx.bars` sequence.

Configuration currently sets:

```text
BACKGROUND_LOOKBACK = 10
CAMPAIGN_MIN_UP_BARS = 3
CAMPAIGN_MIN_DOWN_BARS = 3
CAMPAIGN_MIN_HIGHER_CLOSES = 3
CAMPAIGN_MIN_LOWER_CLOSES = 3
CAMPAIGN_MIN_STRONG_CLOSES = 3
CAMPAIGN_MIN_WEAK_CLOSES = 3
```

So the direct recent-bar campaign dependency fits inside the existing 10-bar background context.

However, campaign strength/weakness also consults structural swings and professional swing scores. Those values therefore depend on the restored structural-history layer.

### SHAKEOUT

SHAKEOUT is the main non-local evidence dependency.

The current implementation:

1. searches backward from the current bar;
2. searches up to `SHAKEOUT_TEST_LOOKAHEAD + SHAKEOUT_RECOVERY_LOOKAHEAD + 1` bars;
3. builds a point-in-time prefix for each candidate;
4. runs `TrendAnalyzer` on the candidate prefix;
5. runs a fresh `EvidenceEngine` on that prefix;
6. validates TEST and RECOVERY forward in time.

Current configuration:

```text
SHAKEOUT_TEST_LOOKAHEAD = 15
SHAKEOUT_RECOVERY_LOOKAHEAD = 5
```

Therefore the direct candidate search depth is **21 bars including the reference boundary**, but the candidate's point-in-time trend/campaign evaluation also requires the structural/trend history available before that candidate.

This means a simple `recent N bars` rule is **not sufficient** for SHAKEOUT.

### SPRING

`evidence/spring.py` searches backward for a recent candidate and requires:

- two prior structural low swings for support;
- candidate bar data;
- point-in-time TEST validation;
- forward confirmation up to `_CONFIRMATION_LOOKAHEAD = 3` bars;
- same-bar supply conflict checks.

Spring therefore depends on both recent metric history and retained structural low-swings.

## Current Replay Implication

The existing `incremental_replay_window()` is safe for the structural layer because `ScannerState` carries stable swing identities.

It is **not yet sufficient as a universal evidence replay contract** because evidence candidate replay can invoke `TrendAnalyzer` again from an arbitrary candidate prefix.

The important distinction is:

```text
metric warm-up
        ≠
structural warm-up
        ≠
evidence candidate-history requirements
```

## Minimum State Recommendation

For the current implementation, do **not** introduce a separate persisted evidence state.

The safe interim contract is:

```text
ScannerState
    ↓
confirmed structural swings
    ↓
active swing candidate
    ↓
stable replay identity
    ↓
metric replay window
    ↓
EvidenceEngine
```

The existing structural state should remain the source of truth.

## Required Future Refactor Before True Evidence-State Minimization

To reduce replay size safely, these evidence dependencies should be made explicit and state-driven:

1. Campaign strength/weakness should consume a persisted trend/context snapshot instead of rerunning `TrendAnalyzer` for every historical candidate.
2. SHAKEOUT candidate validation should consume the persisted causal campaign/trend state for the candidate boundary.
3. SPRING support detection should consume retained structural support levels rather than depending on a large replayed swing set.
4. Evidence candidate/test/recovery identities should be stable bar keys, not dataframe-local positions.

Only after those changes should we define a compact `EvidenceState`.

## Production Safety Rule

Until the above refactor is complete:

> Do not shrink the evidence replay window merely because the metric or swing layers have passed incremental-equivalence tests.

A smaller evidence window that preserves metrics and swings can still change VSA evidence outcomes through campaign or candidate-prefix re-evaluation.

## Next Target

The next implementation target is a **point-in-time campaign snapshot** that captures the causal campaign inputs at a bar boundary. That snapshot can then be reused by SHAKEOUT/SPRING candidate validation without rerunning full historical trend analysis for every candidate.
