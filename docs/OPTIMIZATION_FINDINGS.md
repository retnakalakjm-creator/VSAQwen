# ProVSA Professional Scoring Optimization Findings

## Purpose

This document records the performance work carried out on the professional market-structure scoring pipeline so a future optimization pass can resume from the measured baseline instead of repeating old experiments.

The optimization rule established during this work was:

- make one localized change at a time;
- preserve VSA scoring semantics;
- run the full test suite;
- benchmark the complete `StructureFilter.filter()` path;
- keep only changes with a clear, repeatable end-to-end benefit;
- revert changes that are flat, noisy, or slower.

## Scope

The main performance path investigated was:

```text
confirmed swings
    ↓
ProfessionalScorer.prepare_history_snapshots()
    ↓
StructuralSwingScorer prepared scoring
    ↓
Smart Money scoring
    ↓
professional score
    ↓
StructureFilter.filter()
```

The project principle remains unchanged: ProVSA is a real-market VSA decision system, not a textbook-pattern detector. Performance work must not weaken VSA methodology or force textbook-perfect patterns.

## Successful changes retained

### Prepared metric arrays

Metric columns are converted to reusable NumPy arrays and cached by `ProfessionalScorer._metric_arrays()`.

This avoids repeatedly extracting the same pandas columns during scoring.

### Prepared swing-history snapshots

`ProfessionalScorer.prepare_history_snapshots()` builds reusable `SwingHistorySnapshot` objects for the complete confirmed-swing sequence.

This removes repeated historical traversal/sorting from the per-swing scoring path.

### Sorted historical samples

Snapshots contain sorted versions of the historical samples used by percentile scoring. `percentile_rank_sorted()` can therefore use `bisect_right()` without sorting the sample again.

### Prepared structural scoring

`StructuralSwingScorer.score_prepared()` / `_prepared_values()` score directly from a prepared history snapshot plus current volume/spread instead of rebuilding a full `SwingContext` for every swing.

### Smart Money direct scalar path

The scalar Smart Money path uses dedicated fixed-threshold helpers instead of generic band traversal for the six fixed Smart Money components.

### Genuine batch Smart Money path

A real vectorized batch path was added:

```text
metric arrays
    ↓
score_values_batch_raw()
    ↓
numeric Smart Money arrays
```

`StructureFilter.filter()` consumes these raw batched arrays directly rather than calling `score_values()` once for every swing.

The object-producing `score_values_batch()` API remains available for diagnostics and other callers. Its vectorized math is delegated to the raw batch calculation so the formulas are not duplicated.

### Deferred diagnostic object construction

`StructureFilter.filter()` computes numeric Smart Money results in batch and constructs the full `SmartMoneyScore` / `ScoreBreakdown` objects only after a swing passes the professional threshold.

This preserves returned evaluation data while reducing unnecessary object allocation on rejected swings.

## Important correctness fix

During the batch refactor, the first-bar behavior initially differed from the scalar API.

The correct semantics are:

```text
first bar:
    stopping breakdown = empty
    climactic breakdown = still computed
```

The fix moved climactic breakdown construction outside the first-bar stopping branch. This is now reflected in the retained implementation.

The batch/scalar equivalence test is the key regression test for this behavior:

```text
pytest -q tests/test_professional_scorer.py::test_smart_money_batch_matches_scalar_scoring
```

## Experiments that were rejected or reverted

### Rolling insertion / bisect-based sorted history

An attempt to maintain sorted rolling lists incrementally was slower than the existing bounded-history sorting approach. It was reverted.

Reason: `STRUCTURE_LOOKBACK` is small, so maintaining multiple insertion structures added Python overhead that outweighed the savings.

### Extra list-slice / sort allocation changes

Several attempts to alter the snapshot slice/sort representation increased snapshot preparation time significantly (one measured run reached about `0.25 s`). These were reverted.

The stable snapshot implementation is preferred even if a micro-change looks cleaner locally.

### Additional local/context inlining

Inlining local properties and context access was tested previously and did not produce a reliable end-to-end improvement. Reverted/not retained as a separate optimization target.

### Shared Smart Money intermediate calculations

A change attempting to share `volume_ratio` / `close_position` calculations differently across paths was flat or slightly worse in benchmark results. Not retained.

### Direct `band_score()` specialization attempts

Earlier attempts to specialize the generic band-score helper did not demonstrate a repeatable whole-pipeline improvement. Not retained.

## Benchmark history / reference points

The benchmark command used throughout this work was:

```bash
python tools/profile_multi_symbol.py --symbols 50 --daily-size 5000 --line-profile
```

Representative measured states:

| State / experiment | `prepare_history_snapshots()` | `StructureFilter.filter()` | Decision |
|---|---:|---:|---|
| Stable prepared baseline | ~0.175–0.178 s | ~0.533–0.535 s | Keep |
| Slightly noisy stable run | ~0.183 s | ~0.535 s | Keep; normal variation |
| Snapshot allocation experiment | ~0.250 s | ~0.85 s range | Revert |
| Current user-reported run | ~0.18 s | ~0.56 s | Accept / freeze |

The current user-reported profile is:

```text
0.18 seconds - professional_scorer.py:79  - ProfessionalScorer.prepare_history_snapshots
0.56 seconds - structure_filter.py:25    - StructureFilter.filter
```

The `0.56 s` result is close enough to the established ~`0.53–0.54 s` range that it should be treated as normal benchmark variation unless repeated measurements show a persistent regression.

## Important commit references

These are useful checkpoints when revisiting the work:

- `c058948fa912a705c579bf83aa9d1ea7b04adf44` — introduced the raw batched Smart Money path.
- `a16fdda20b47710d2515de328617d88b2ae05eca` — fixed the first-bar/climactic scope issue in the batch object API.
- `e5ee5a80bb27533a8307aa3cefeb3f9be3a60f38` — verified clean `professional_scorer.py` snapshot baseline.
- `f0693674af9865456afa60d69455d2f7c6775a9e` — structural scorer local-binding optimization.
- `c47e6f5f27d6338007b3b8ed31395fd1d090f10c` — `StructureFilter` metric-index reuse optimization.

The exact current `main` tip should always be checked before reusing any older checkpoint.

## Current performance conclusion

The easy and meaningful micro-optimizations in this layer are largely exhausted.

The current implementation has:

- prepared historical state;
- sorted percentile samples;
- prepared structural scoring;
- genuine batched/vectorized Smart Money calculation;
- deferred Smart Money diagnostic-object creation;
- cached/local hot-path references.

Further small Python-level changes are unlikely to produce a meaningful scanner-level gain without increasing complexity or risking regressions.

### Recommended stopping point

Treat roughly:

```text
prepare_history_snapshots()  ≈ 0.18 s
StructureFilter.filter()     ≈ 0.53–0.56 s
```

as the practical optimization threshold for this layer unless a future profile identifies a clearly dominant new hotspot.

Do not continue micro-tuning solely to move these numbers by a few milliseconds.

## If optimization is revisited later

Start by:

1. reading this file and `SUMMARY.txt`;
2. inspecting the live `main` code rather than assuming an old checkpoint is current;
3. running the standard benchmark twice to establish a fresh local baseline;
4. profiling the full pipeline, not an isolated helper;
5. preferring higher-level optimizations over deeper micro-optimizations.

Likely higher-level opportunities, if performance becomes important again, are:

- incremental processing so unchanged symbols are not rescanned;
- symbol-level parallelism where appropriate;
- reducing duplicate data preparation across pipeline stages;
- data-fetch and I/O efficiency;
- narrowing the amount of history entering expensive analysis without changing VSA semantics.

Any future optimization must continue to preserve scoring equivalence and normal scanner eligibility behavior.
