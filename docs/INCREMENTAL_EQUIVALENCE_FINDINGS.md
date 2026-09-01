# Incremental Swing Equivalence Findings

## Status

**COMPLETE — checkpoint-continuation equivalence validated across the 30-symbol universe.**

Validated at commit:

`3a64984a5a6b9761fe419a7bb6735706d5d2e887`

## Test

The audit compared a full historical `SwingEngine` calculation with a checkpointed run that:

1. calculated the prefix through a checkpoint;
2. captured `ScannerState` using stable bar identities;
3. reopened the data required to restore those state identities;
4. continued with `SwingEngine.calculate_from_state()`;
5. compared the retained swing state and final scanner state against the full-history result.

Checkpoint ratios tested:

- 60%
- 70%
- 80%

Universe:

- 30 symbols
- 3 checkpoints per symbol
- 90 total checkpoint comparisons

## Result

**90/90 checkpoint comparisons were equivalent.**

Every symbol passed all three checkpoints. The audit output reported:

- `Swings = True`
- `State = True`
- `Equivalent = True`

for every checkpoint.

Therefore, within the tested 30-symbol universe and the tested 60%/70%/80% historical checkpoints, the persisted swing `ScannerState` can be restored and continued to reproduce the same retained swing state as a full historical rebuild.

## Important interpretation

This result validates **checkpoint continuation / state restoration correctness** for the current swing state model.

It does **not** establish a universal historical safety-window size. The earlier experimental `20/40/60/...` window test was removed because the current `calculate_from_state()` API resumes from persisted causal state rather than replaying an arbitrary number of preceding bars. Therefore, those window sizes would not have represented a real variable in the computation.

The validated conclusion is specifically:

> Full historical swing calculation and checkpoint-continuation from persisted `ScannerState` are equivalent across 30 symbols at 60%, 70%, and 80% checkpoints.

## Production implications

This closes the **swing-state checkpoint equivalence** validation stage.

It does not by itself authorize persistent scanner deployment or prove equivalence for downstream trend, VSA evidence, professional scoring, qualification, actionability, or final ranking. Those layers require their own dependency-aware equivalence validation before persistence is promoted to the complete scanner pipeline.

## Source artifact

The raw successful audit output was recorded in the repository as `incre_result.txt` at the validation commit above.
