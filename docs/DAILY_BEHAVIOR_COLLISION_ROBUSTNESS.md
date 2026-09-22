# Daily Behavior Collision Robustness

## Purpose

PR #366 showed that some broad exact-evidence variants inside the same coarse
DailyBehavior signature have different forward outcomes.

That result is descriptive. Before introducing any shadow `BehaviorMechanism`
taxonomy, this audit asks whether the broad contrasts survive composition
checks.

The audit remains CSV-only and non-actionable.

## Inputs

Two existing artifacts are consumed.

### Raw #365 outcomes

```text
reports/daily-behavior-sequences/collision-universe/
  milestone6_standard_india_large_cap_30_frozen_2026-09-18/
  daily_sequence_outcomes.csv
```

This remains a local generated artifact. It does not need to be committed.

It provides the row-level fields needed for:

- symbol balancing;
- leave-one-symbol-out checks;
- within-symbol nearby-time matching.

### Committed #366 pairwise contrasts

```text
reports/daily-behavior-sequences/collision-outcomes/
  milestone6_standard_india_large_cap_30_frozen_2026-09-18/
  daily_behavior_collision_within_coarse_pairwise_contrasts.csv
```

This defines the exact pooled contrasts already reported by #366.

## Source identity

The summary records SHA-256 fingerprints for both source CSVs.

For every broad pair/horizon, the raw outcome rows are recomputed and must
reproduce the #366 pooled favorable-return contrast within floating-point
tolerance.

A mismatch fails the audit.

## Broad-pair gate

Default eligibility requires both exact evidence variants to have, at every
requested horizon:

```text
complete outcomes >= 100
symbol breadth    >= 20
horizons          = 1,3,5,10,15
```

The broad-pair gate does not require outcome-sign stability.

That allows the study to distinguish:

- broad pairs whose pooled ordering changes with horizon;
- broad pairs whose pooled ordering is stable;
- pairs whose pooled ordering survives stronger composition checks.

## Robustness views

### 1. Pooled

The existing global mean difference:

```text
mean(A favorable return) - mean(B favorable return)
```

is recomputed from raw outcomes and reconciled to #366.

### 2. Symbol-balanced

For each symbol:

```text
mean(A within symbol) - mean(B within symbol)
```

is calculated only when both variants occur in that symbol.

The audit then reports the mean and median of those within-symbol differences.

Every paired symbol therefore contributes one value regardless of how many
observations it contributes to the pooled sample.

### 3. Leave-one-symbol-out

Each contributing symbol is removed once.

The audit records:

- minimum leave-one-out pooled delta;
- maximum leave-one-out pooled delta;
- fraction retaining the original pooled sign;
- whether every leave-one-out iteration retains the pooled sign.

This exposes contrasts driven by a single symbol.

### 4. Within-symbol nearest-time matching

Within each symbol, A and B observations are matched one-to-one by smallest
absolute signal-bar-index gap.

Default maximum gap:

```text
20 daily bars
```

Each observation can be used only once.

The audit reports:

- matched pair count;
- matched symbol count;
- mean bar gap;
- mean and median matched favorable-return delta;
- mean matched MFE delta;
- mean matched MAE delta.

This does not prove causality. It is a composition control intended to compare
the two exact mechanisms in more similar symbol/time environments.

## Pair-level summary

For every broad exact-variant pair the audit records whether:

- pooled sign is stable across all horizons;
- symbol-balanced sign is stable across all horizons;
- matched sign is stable across all horizons;
- leave-one-symbol-out retains the pooled sign at every horizon;
- pooled, symbol-balanced, and matched methods agree in sign at each horizon;
- all of the above hold together.

The final combined boolean is descriptive only:

```text
all_methods_sign_stable_across_horizons
```

It is not a promotion rule, score, ranking, or actionability gate.

## Outputs

```text
daily_behavior_collision_robustness_summary.json
daily_behavior_collision_broad_pairs.csv
daily_behavior_collision_horizon_robustness.csv
daily_behavior_collision_pair_summary.csv
```

Every output remains:

```text
is_actionable = false
```

## Safety boundary

No changes to:

- detector semantics;
- EvidenceCode;
- DailyBehaviorDimension;
- WeeklySetup authority;
- scoring;
- ranking;
- confidence;
- qualification;
- actionability;
- DailyEntry;
- alerts or orders.

No detector replay or market-data read occurs.

## Validation

```powershell
python -m ruff check audit/daily_behavior_collision_robustness.py scripts/analyze_daily_behavior_collision_robustness.py tests/test_daily_behavior_collision_robustness.py

python -m pytest -q tests/test_daily_behavior_collision_robustness.py tests/test_daily_behavior_collision_outcomes.py tests/test_daily_behavior_sequence_outcomes.py

git diff --check origin/main...HEAD
```

## Run

```powershell
python scripts\analyze_daily_behavior_collision_robustness.py `
  --raw-outcomes-csv reports\daily-behavior-sequences\collision-universe\milestone6_standard_india_large_cap_30_frozen_2026-09-18\daily_sequence_outcomes.csv `
  --pairwise-contrasts-csv reports\daily-behavior-sequences\collision-outcomes\milestone6_standard_india_large_cap_30_frozen_2026-09-18\daily_behavior_collision_within_coarse_pairwise_contrasts.csv `
  --output-dir reports\daily-behavior-sequences\collision-robustness\milestone6_standard_india_large_cap_30_frozen_2026-09-18
```

This operates only on existing CSV artifacts and should be much faster than the
original replay.
