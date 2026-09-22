# M12 — TEST Detector Verdict

## Status

**PARKED — current detector semantics retained and frozen.**

This is a detector-layer verdict only.

It does not alter detector logic, professional scoring, qualification,
actionability, ranking, alerts, or orders.

## Stop-rule review

### 1. Is the semantic contract correct?

Yes, for the currently audited production population.

Production identity:

```text
Selling campaign / meaningful recent selling pressure
Bearish / down bar
Low volume
Narrow spread
No confirmed-downtrend contradiction without recent structural weakness
```

The fifth clause is deliberate production behavior. It was introduced after the
historical audit removed strong-downtrend/no-structural-weakness cases from the
production population.

It is not a diagnostic confirmation.

### 2. Is it distinct from other detectors?

Yes.

The closest low-effort event is `NO_SUPPLY`.

`TEST`:

```text
selling campaign
down bar
low volume
narrow spread
no strong-downtrend contradiction
```

`NO_SUPPLY`:

```text
bearish-environment predicate
down bar
low volume
narrow spread
```

They share the low-volume / narrow-spread / down-bar core, but the context
contracts differ. The historical TEST interaction audit found only a small
same-bar overlap with `NO_SUPPLY`, not identity equivalence.

`SHAKEOUT` is also distinct: TEST is a current-bar low-effort observation,
while SHAKEOUT is a recovery-anchored multi-stage event that may use a later
TEST as part of its sequence.

### 3. Are confirmations behaving as intended?

Yes.

Current diagnostic confirmations are:

```text
Volume decreasing
Strong close
Higher low
```

Shared `evaluate_detector()` records them but does not gate emission on them.

Other observations such as supply drying are interaction/context evidence, not
formal TEST detector confirmations.

### 4. Is there an obvious correction?

No production detector correction is justified.

The current five-clause production population was explicitly audited and later
validated across eight symbols. No causal/look-ahead defect is present: TEST is
a current-bar event using current, previous, and already-available context.

## Detector-layer decision

```text
semantic contract      RETAIN
distinctness           PASS
confirmation behavior  PASS
obvious detector fix   NONE

M12 detector status    PARKED
detector semantics     FROZEN
production emission    UNCHANGED
```

"PARKED" means no further detector-specific calibration is justified under the
current evidence.

## Canonical-spec correction

The canonical TEST specification had drifted in two ways.

First, it listed only four mandatory requirements and described persistent
downtrend mainly as interpretive context. Current production has a deliberate
fifth mandatory gate:

```text
not (
    confirmed downtrend
    and not recent structural weakness
)
```

Second, the spec described TEST simply as "non-scoring" without distinguishing
the scanner layers.

The corrected policy is:

```text
professional demand-score weight     = 0.0
emitted Evidence.weight metadata      = dynamic via _test_weight(ctx)
directional VSA confirmation role     = YES
standalone structural qualification   = NO
standalone trade actionability        = NO
```

`ProfessionalScoringEngine` ignores TEST for demand pressure because TEST is
absent from `config.DEMAND_EVIDENCE_WEIGHTS`.

The scanner may still treat TEST as bullish directional VSA confirmation for an
already-qualified structural setup. That is contextual confirmation, not
standalone qualification or actionability.

## Validation boundary

The historical production validation recorded:

```text
events                         47
symbols with events             8 / 8
positive 8-bar outcomes        27
negative 8-bar outcomes        14
flat outcomes                   6
persistent-downtrend conflicts  0 / 47
```

That evidence supports retaining the audited detector population. It does not
justify adding new textbook confirmation gates or a professional scoring
weight.

## Reopening rule

Reopen TEST detector semantics only for:

1. independent out-of-sample evidence showing a contract defect;
2. a first-principles contradiction in the low-effort probe definition;
3. a newly discovered causal/look-ahead defect;
4. a deliberate proposal to change the strong-downtrend contradiction gate,
   followed by a new audit/replay cycle.

Do not reopen TEST merely to tune emitted metadata weight, professional scoring,
interaction groups, or actionability policy.

## Architecture boundary

TEST remains a contextual observation inside the evolving supply-demand story.

It can confirm that selling pressure is being probed on low effort, but it does
not by itself establish accumulation, demand control, support success, or a
trade entry.
