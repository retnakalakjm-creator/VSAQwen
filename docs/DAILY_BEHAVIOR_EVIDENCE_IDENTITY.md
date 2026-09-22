# Daily Behavior Evidence Identity

## Purpose

The existing DailyBehavior layer intentionally groups named VSA events into a
small set of direction-relative behavior dimensions.

That abstraction is useful, but the historical sequence study previously used
only those coarse dimensions as its sequence identity. Distinct event narratives
could therefore collapse into the same cohort.

Examples:

```text
BUYING_CLIMAX
UPTHRUST
        ↓
REJECTION_OF_OPPOSING_MOVE
```

and, on the bullish side:

```text
STOPPING_VOLUME
SELLING_CLIMAX
SHAKEOUT
SPRING
        ↓
REJECTION_OF_OPPOSING_MOVE
```

This audit layer preserves the exact supporting evidence-code identity beside the
coarse behavior identity without changing production behavior.

## Two identities

### Coarse behavior signature

The existing signature remains:

```text
relative bar offset
+
DailyBehaviorDimension tuple
```

It remains the grouping key for the current outcome study.

### Exact evidence signature

A second read-only signature records:

```text
relative bar offset
+
sorted unique supporting EvidenceCode tuple
```

This keeps named-event provenance visible when multiple event mechanisms map to
the same coarse behavior dimension.

## Collision audit

The historical bundle now reports coarse signatures that contain more than one
exact evidence signature.

A collision means:

```text
same weekly direction
+
same coarse behavior sequence
+
different exact supporting-code sequence
```

This is an information-loss diagnostic only. It does not mean one event family is
better than another.

The bundle adds:

```text
daily_sequence_signature_collisions.csv
```

and summary counters:

```text
coarse_signature_collision_count
collision_observation_count
```

The existing sequence-record and outcome CSVs also expose
`evidence_signature` beside the existing `signature`.

## Safety boundary

This PR does not change:

- detector semantics;
- DailyBehaviorDimension mappings;
- weekly direction authority;
- sequence freshness rules;
- outcome execution timing;
- outcome cohort grouping;
- scoring;
- confidence;
- ranking;
- qualification;
- actionability;
- alerts or orders.

The exact evidence signature is audit provenance only.

## Why this precedes behavior remapping

The next behavior-design decision should be evidence-led.

Before introducing mechanism-level dimensions such as climactic exhaustion,
structural rejection, stopping action, or recovery, we first need to measure how
often the current coarse model collapses genuinely distinct event histories and
whether those distinctions have different forward-outcome behavior.

This keeps named VSA events as evidence inside the supply-demand story without
forcing textbook event labels to become production gates.

## Validation

Focused validation:

```powershell
python -m ruff check audit/daily_behavior_sequence_outcomes.py audit/daily_behavior_sequence_runner.py tests/test_daily_behavior_sequence_outcomes.py tests/test_daily_behavior_sequence_runner.py

python -m pytest -q tests/test_daily_behavior_sequence_outcomes.py tests/test_daily_behavior_sequence_runner.py tests/test_daily_behavior_sequence.py tests/test_daily_behavior_evidence.py

git diff --check origin/main...HEAD
```

Expected contract:

```text
existing coarse signatures unchanged
existing outcome grouping unchanged
exact evidence signatures distinguish collapsed named-event narratives
all new artifacts remain is_actionable = false
```
