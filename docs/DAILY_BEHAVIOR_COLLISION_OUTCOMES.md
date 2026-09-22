# Daily Behavior Collision Outcome Stratification

## Purpose

The frozen 30-symbol collision study established that the current coarse
DailyBehavior sequence abstraction hides multiple exact VSA evidence narratives
in a large share of fresh sequences.

This follow-up audit does **not** replay detectors or market data.

It consumes the already-generated sequence-study CSV bundle and asks four
narrower questions:

1. What is the collision rate after normalizing separately by weekly direction?
2. Which coarse DailyBehavior dimension families contain most collisions?
3. How broad is each exact evidence variant across symbols?
4. Within one fixed coarse signature, do exact evidence variants show materially
   different forward outcomes?

The purpose is to gather evidence for or against a later mechanism layer. It
does not introduce a mechanism taxonomy itself.

## Input

The audit reads only:

```text
daily_sequence_records.csv
daily_sequence_outcomes.csv
daily_sequence_signature_collisions.csv
```

from a completed sequence study directory.

For the frozen 30-symbol study, the source directory is:

```text
reports/daily-behavior-sequences/collision-universe/
  milestone6_standard_india_large_cap_30_frozen_2026-09-18/
```

No EvidenceEngine call occurs.

No weekly scanner call occurs.

No network or market-data read occurs.

## Reconciliation gate

Before analysis, the runner independently reconstructs collision membership from
fresh sequence records and verifies:

```text
fresh records whose
(direction, coarse signature)
appears in collision ledger

==

sum(daily_sequence_signature_collisions.observation_count)
```

A mismatch fails the audit.

This prevents stale, partial, or mixed study artifacts from being analyzed
silently.

## Direction-normalized collision rate

The output:

```text
daily_behavior_collision_direction_summary.csv
```

reports per weekly direction:

- fresh sequence count;
- collision observation count;
- collision rate;
- distinct coarse signatures;
- colliding coarse signatures;
- distinct exact evidence signatures;
- contributing symbol count.

This avoids interpreting raw bearish/bullish collision counts without accounting
for different direction populations.

## Dimension-family concentration

The audit derives a non-semantic family label from the set of coarse
`DailyBehaviorDimension` values present in a sequence.

Example:

```text
-3:aligned_pressure_emerging;
 0:aligned_pressure_emerging

-> aligned_pressure_emerging
```

and:

```text
-3:aligned_pressure_emerging;
 0:rejection_of_opposing_move

-> aligned_pressure_emerging+rejection_of_opposing_move
```

This is only a grouping convenience. It does not introduce a new production
behavior type.

Output:

```text
daily_behavior_collision_dimension_family_summary.csv
```

## Exact evidence breadth

The output:

```text
daily_behavior_collision_evidence_variant_breadth.csv
```

retains:

```text
weekly direction
coarse signature
exact evidence signature
observation count
distinct symbol count
share of universe symbols
```

This helps distinguish a broad mechanism from a one-symbol or low-breadth
artifact.

## Exact-variant forward outcomes

The output:

```text
daily_behavior_collision_evidence_variant_outcomes.csv
```

groups the existing forward outcomes by:

```text
weekly direction
+
fixed coarse signature
+
exact evidence signature
+
horizon
```

It reports descriptive:

- observation count;
- available and complete outcome count;
- symbol breadth;
- mean and median favorable return;
- mean MFE;
- mean MAE.

The coarse signature remains fixed, so differences are evidence-identity
heterogeneity **inside the same current DailyBehavior interpretation**.

## Within-coarse heterogeneity

Two additional outputs are created.

### Spread summary

```text
daily_behavior_collision_within_coarse_outcome_spreads.csv
```

For each direction/coarse-signature/horizon with at least two adequately sampled
exact variants, it records the range of:

- mean favorable return;
- mean MFE;
- mean MAE.

### Pairwise contrasts

```text
daily_behavior_collision_within_coarse_pairwise_contrasts.csv
```

Exact variants are paired in deterministic lexical order and report:

```text
A mean - B mean
```

for favorable return, MFE, and MAE.

These are descriptive contrasts only. They are not significance tests,
promotion rules, scores, or rankings.

The minimum complete-outcome sample per variant defaults to:

```text
20
```

and is configurable.

## Safety boundary

This audit changes no production code and does not change:

- detector semantics;
- EvidenceCode definitions;
- DailyBehaviorDimension mappings;
- weekly authority;
- qualification;
- scanner scoring;
- ranking;
- confidence;
- actionability;
- DailyEntry;
- alerts or orders.

Every output remains:

```text
is_actionable = false
```

## Run

After PR validation, the completed 30-symbol study can be post-processed with:

```powershell
python scripts\analyze_daily_behavior_collision_outcomes.py `
  --study-dir reports\daily-behavior-sequences\collision-universe\milestone6_standard_india_large_cap_30_frozen_2026-09-18 `
  --output-dir reports\daily-behavior-sequences\collision-outcomes\milestone6_standard_india_large_cap_30_frozen_2026-09-18 `
  --min-complete-per-variant 20
```

This should be fast relative to the original replay because it reads existing
CSV artifacts only.

## Interpretation rule

A coarse collision is not evidence that the current dimension is wrong.

A mechanism layer becomes worth designing only if exact variants show a
combination of:

- repeated occurrence;
- adequate symbol breadth;
- stable direction-specific presence;
- meaningful within-coarse outcome heterogeneity;
- interpretable VSA mechanism differences.

Only after those conditions are reviewed should a later PR propose a shadow
`BehaviorMechanism` taxonomy.
