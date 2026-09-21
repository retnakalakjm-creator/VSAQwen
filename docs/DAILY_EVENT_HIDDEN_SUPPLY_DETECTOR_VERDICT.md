# M12 — HIDDEN_SUPPLY Detector Verdict

## Status

**PARKED — current detector semantics retained and frozen.**

This is a detector-layer verdict only.

It does not promote scoring, alter evidence aggregation, change DailyBehavior,
qualification, actionability, alerts, or orders.

## Stop-rule review

### 1. Is the semantic contract correct?

Yes for the current supporting-supply role.

Production identity:

```text
Up / bullish bar
High volume
Close in lower part of the bar
```

The close requirement is implemented through `closes_lower()`, which means
`ClosePosition.LOWER` or `ClosePosition.ON_LOW`.

This is coherent as a current-bar observation of apparent upward price movement
that attracts elevated activity but finishes with weak intrabar acceptance.

The existing audit population reproduced these semantics without mandatory
semantic failures.

### 2. Is it distinct from other detectors?

Yes.

Closest supply-side events include `BUYING_CLIMAX`,
`SUPPLY_COMING_IN`, and `INCREASING_SUPPLY`.

`HIDDEN_SUPPLY`:

```text
up bar
high volume
lower close
```

`BUYING_CLIMAX`:

```text
buying campaign
bullish bar
very high volume
above-average spread
non-strong high-price acceptance
```

`SUPPLY_COMING_IN`:

```text
buying campaign
down bar
high volume
above-average spread
weak close
volume increasing
```

`INCREASING_SUPPLY`:

```text
down bar
volume increasing
spread increasing
```

The events can overlap where their observations are simultaneously true, but
their mandatory identities are not aliases.

`HIDDEN_SUPPLY` is the simpler supporting observation: elevated activity on
an up bar that fails to retain a strong close.

### 3. Are confirmations behaving as intended?

There is no separate confirmation list.

All three clauses are mandatory identity requirements and the detector emits
directly through `add_evidence()`.

Therefore there is no confirmation-gating defect to correct.

### 4. Is there an obvious correction?

No production-safe detector correction is justified.

The current implementation is:

- current-bar only;
- point-in-time;
- mechanically aligned with the documented identity;
- distinct from the neighboring supply detectors.

The earlier audit did not justify a rejection rule, interaction penalty, or
semantic tightening.

## Detector-layer decision

```text
semantic contract      RETAIN
distinctness           PASS
confirmation issue     NONE
obvious detector fix   NONE

M12 detector status    PARKED
detector semantics     FROZEN
production emission    UNCHANGED
```

"PARKED" means no further detector-specific research is justified under the
current evidence. It does **not** disable the production collector.

## Scoring boundary

The detector verdict does not redefine the downstream scoring architecture.

The current project records `HIDDEN_SUPPLY` as non-promoted standalone
professional scoring evidence while still retaining it as collected supporting
evidence and as a read-only DailyBehavior input for bearish
`ALIGNED_PRESSURE_EMERGING`.

Profile metadata and generic evidence aggregation are separate architectural
concerns and are not modified by this detector review.

Any future scoring cleanup must be handled independently and must not reopen the
detector identity by default.

## Reopening rule

Reopen `HIDDEN_SUPPLY` detector semantics only for:

1. independent out-of-sample evidence showing a contract defect;
2. a first-principles semantic contradiction;
3. a newly discovered causal/look-ahead defect;
4. a demonstrated detector identity collision that the current contract cannot
   explain.

Do not reopen it merely to tune weights, ranking influence, or subgroup
performance.

## Architecture boundary

`HIDDEN_SUPPLY` remains one supporting observation inside the evolving
supply/demand story.

It should contribute evidence about pressure and acceptance; it should not
become a standalone trade trigger or a mandatory textbook-label prerequisite.
