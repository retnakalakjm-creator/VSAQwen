# M12 — SPRING Candidate-Time Structural Causality Correction

## Status

Production correctness correction implemented for validation.

This PR fixes one causal contract defect in the existing `SPRING` detector. It
does not redesign Spring semantics, recalibrate thresholds, change weight,
change same-bar conflict policy, or promote actionability.

## Stop-rule review

### 1. Is the semantic contract correct?

Yes, with one causal implementation defect.

The intended Spring sequence remains:

```text
established structural support
    ->
controlled support penetration / recovery
    ->
low-effort test
    ->
bullish confirmation
```

The detector is confirmation-anchored: the completed Spring is emitted on the
later bullish confirmation bar.

### 2. Is it distinct from other detectors?

Yes.

The closest reversal detector is `SHAKEOUT`, but the identities are different.

`SPRING` is support-structure centered:

```text
prior structural support
controlled penetration
low-effort test
bullish confirmation
```

`SHAKEOUT` is climactic selling/recovery centered:

```text
selling pressure
bearish/down bar
wide spread
very high volume
lower low
valid test
valid recovery
```

They can describe related bullish reversal stories without being semantic
aliases.

### 3. Are confirmations behaving as intended?

Yes.

Spring's test and bullish confirmation are mandatory stages of the event
sequence. They are not the shared `evaluate_detector()` diagnostic
confirmations used by current-bar detectors.

The completed event is emitted only when the bullish confirmation index equals
the current bar.

### 4. Is there an obvious correction?

Yes.

Before this correction, candidate support lookup required:

```text
structural swing type == LOW
pivot bar_index < candidate_index
```

but did not also require:

```text
confirmation_index <= candidate_index
```

The daily replay correctly exposes only structural swings confirmed by the
current target/confirmation bar. However, `collect_spring()` then re-evaluates
an earlier candidate using that later structural tuple.

Therefore a structural low could have:

```text
pivot before Spring candidate
confirmation after Spring candidate
confirmation at/before current Spring confirmation bar
```

and incorrectly participate in the candidate's historical support definition.

That violates the intended point-in-time candidate contract.

## Correction

`_prior_low_swings()` now admits a support low only when:

```text
swing.type == LOW
swing.bar_index < candidate_index
swing.confirmation_index <= candidate_index
```

This mirrors the candidate-time causality principle already used elsewhere in
the evidence stack.

## Regression coverage

Focused tests prove both sides:

1. a structural-low pivot before the candidate but confirmed after the
   candidate cannot create the required support-touch count;
2. the same support lows remain eligible when both were confirmed by the
   candidate bar.

## Scope boundary

Unchanged:

- Spring support-touch count;
- penetration thresholds;
- test thresholds;
- confirmation lookahead;
- base weight `0.75`;
- same-bar BC/UPTHRUST quality reduction;
- evidence direction;
- DailyBehavior;
- scoring/ranking policy;
- qualification/actionability;
- alerts/orders.

## Validation rule

Focused code validation:

```powershell
python -m ruff check evidence/spring.py tests/test_spring.py tests/test_audit_vsa_events.py
python -m pytest -q tests/test_spring.py tests/test_audit_vsa_events.py
```

Then run the canonical cached daily inventory into a dedicated output directory
and compare against the existing post-BC/UT baseline.

Only Spring event identity/attributes may change as a direct result of this
correction. Any unrelated event drift requires investigation before merge.

The inventory CSV serializes evidence codes using lowercase enum values
(`spring`, not `SPRING`).

A causal visibility correction is not necessarily monotonic in Spring count.
Because support selection uses the latest two *eligible* structural lows,
removing a later low that was not yet confirmed at candidate time can expose an
older pair of already-confirmed lows that forms valid support. Therefore the
correction may legitimately add as well as remove Spring emissions. Any changed
Spring must still be attributable to candidate-time structural visibility.

## Post-validation decision

If the focused tests pass and frozen replay shows only causally explained Spring
changes, merge the correction and mark Spring detector semantics frozen under
M12.

If the correction exposes broader unexpected drift, stop and investigate that
implementation issue only; do not open a new Spring calibration program.


## Frozen 30-symbol replay result

The canonical cached replay on the frozen 30-symbol snapshot completed with:

```text
requested symbols      30
succeeded symbols      30
failed symbols          0
evaluated bars     198,382

before Spring          254
after Spring           309
Spring removed           0
Spring added            55

non-Spring exact equal  YES
```

Aggregate inventory changed exactly as expected from the additional Spring
emissions:

```text
evidence emissions
    before 157,731
    after  157,786
    delta      +55

event bars
    before  91,007
    after   91,040
    delta      +33
```

The larger Spring count is causally consistent with the corrected support
visibility rule. Filtering out a structural low that was not yet confirmed at
candidate time can expose an older pair of already-confirmed lows; that older
pair may satisfy the support-clustering rule and produce a valid candidate that
the old implementation incorrectly masked.

No non-Spring emission changed.

## Final M12 detector verdict

```text
semantic contract      RETAIN
distinctness           PASS
confirmation behavior  PASS
causal defect           CORRECTED

detector status         FROZEN
M12 status              CORRECTED / CLOSED
production emission     UPDATED BY CAUSAL FIX ONLY
scoring calibration     PROVISIONAL / UNCHANGED
```

Do not reopen Spring detector semantics for threshold tuning or outcome
optimization from this same sample. Reopen only for new independent evidence,
a new causal defect, or a first-principles semantic contradiction.
