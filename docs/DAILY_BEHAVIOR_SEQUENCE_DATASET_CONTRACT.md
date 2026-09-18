# Frozen Daily Behavior Sequence Dataset Contract

## Purpose

K3 accepts prepared point-in-time inputs in memory. K4 makes that boundary
portable and reproducible by defining a frozen JSON interchange format.

K4 does not create a real historical dataset by itself. It defines the contract
that a genuine daily-evidence source must satisfy before K3 can consume it.

## Required provenance

Every frozen dataset records:

```text
dataset_id
source.kind
source.reference
source.prepared_at_utc
source.notes
```

Source provenance is mandatory. A prepared dataset cannot be written without a
nonblank source kind, reference, and preparation timestamp.

## Timeframe boundary

Frozen K4 datasets are explicitly:

```text
price_timeframe = 1D
evidence_timeframe = 1D
```

A dataset labeled with weekly evidence is rejected.

This is intentional. Existing weekly audit/replay artifacts cannot be relabeled
as daily evidence merely to populate the K3 runner.

## Symbol payload

Each symbol contains the exact K3 input boundary:

```text
symbol
daily close/high/low bars with stable index identity
weekly-direction assignments by daily bar_index
full Evidence records
embedded K3 input fingerprint
```

All Evidence fields are retained:

- code;
- category;
- direction;
- strength;
- weight;
- observation;
- description;
- bar_index;
- week_beginning;
- test_index;
- recovery_index;
- quality.

## Integrity

The writer recomputes K3 fingerprints before writing.

The loader reconstructs the prepared K3 input, recomputes its fingerprint, and
compares it with the embedded fingerprint.

Therefore:

```text
edited price
edited direction assignment
edited evidence
        ↓
fingerprint mismatch
        ↓
load fails closed
```

Schema version is also validated on both write and load.

## K3 handoff

A loaded frozen dataset can be passed directly to:

```python
run_daily_behavior_sequence_historical_study(
    dataset.inputs,
    expected_fingerprints=dataset.fingerprints,
)
```

This creates a second fingerprint gate at study execution.

## Current real-data status

The currently available saved LT audit artifacts inspected during K4 preparation
are weekly-timeframe artifacts. They are useful for weekly validation but are not
valid K4 daily-evidence inputs.

K4 therefore does not manufacture a "real" dataset from them.

The next real-data step requires one genuine point-in-time daily evidence source,
for example:

- a reviewed daily evidence export;
- a manually labeled daily casebook with exact bar identities;
- a future offline daily evidence producer validated separately from production.

Only after such a source exists should a real frozen K4 dataset be committed or
interpreted.

## Safety

The dataset contract is analysis-only.

It does not:

- derive evidence from OHLCV;
- infer weekly direction;
- modify K1/K2/K3 semantics;
- alter F3 fresh-signal behavior;
- create a score, threshold, or ranking;
- change production actionability;
- create alerts or orders.

A frozen dataset is evidence for research reproducibility, not evidence for
sequence promotion.
