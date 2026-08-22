# SUPPLY_COMING_IN Audit Record

## Final status

`SUPPLY_COMING_IN` is production-active and audit-complete for the current detector definition.

```text
production path              = YES
collector                     = evidence/supply.py::_collect_supply_coming_in
engine collection             = YES (via collect_supply)
registry/profile weight      = 1.00
production runtime weighting = dynamic
empirical reference weight   = 0.38
production interaction penalty = NONE
production status             = ACTIVE
```

The empirical `0.38` value is retained only as a historical calibration/reference point. It is **not** the fixed production runtime weight.

## Audit completion

The event completed the current audit-first validation sequence:

1. Candidate audit — PASS
2. Semantic-quality audit — PASS
3. Interaction / contradiction audit — PASS
4. Interaction outcome audit — PASS
5. Decision-value audit — PASS
6. Weight-sensitivity audit — PASS
7. Full scanner ranking replay — PASS for the measured production-path behavior
8. Production-path readiness audit — PASS

## Frozen candidate population

Across 8 symbols:

```text
symbols requested          = 8
symbols with results      = 8
bars scanned              = 11,345
cheap candidates          = 1,022
campaign-qualified bars   = 370
production candidate events = 189
normal detector rejections  = 181
expected candidate events = 189
```

The 181 non-emissions among campaign-qualified bars are **normal detector rejections**, not production-path mismatches.

## Frozen semantics

The current point-in-time `SUPPLY_COMING_IN` detector requires:

1. Down / bearish bar.
2. High volume.
3. Above-average spread.
4. Weak close.
5. Increasing volume versus the previous bar.

The audit deliberately preserves meaningful imperfect real-market evidence rather than requiring textbook-perfect VSA formations.

## Semantic-quality verification

All 189 emitted events satisfied the production semantics:

```text
down_bar              = 189 / 189
high_volume           = 189 / 189
above_average_spread  = 189 / 189
weak_close             = 189 / 189
volume_increasing      = 189 / 189
semantic_failures      = 0
status                 = PASS
```

## Outcome audit

```text
candidate events            = 189
positive outcomes            = 119
negative outcomes            = 70
flat outcomes                = 0
decisive outcomes             = 189
positive decisive rate       = 62.96%
mean 8-bar return            = +3.76%
```

Eligible-market comparison:

```text
eligible-market events       = 11,345
eligible-market positive rate = 60.79% (earlier baseline)
positive-rate lift             = about +2.17 pp
candidate mean return          = +3.76%
eligible-market mean return   = +3.83%
mean-return lift               = approximately -0.05 to -0.07 pp
```

The event therefore shows **positive directional classification lift but essentially neutral return-magnitude lift** relative to the eligible market.

## Supply interaction / contradiction audit

Same-bar interaction audit on the frozen 189 production events:

```text
events                        = 189
supply-conflict events        = 147
supply-conflict rate          = 77.78%
demand interaction events     = 0
self-conflict excluded        = YES
target-bar-only               = YES
status                        = PASS
```

The entire supply-conflict population was:

```text
INCREASING_SUPPLY = 147 events
```

No `HIDDEN_SUPPLY`, `SUPPLY_DRYING_UP`, `NO_DEMAND`, `BUYING_CLIMAX`, or `UPTHRUST` interaction was established in the audited population.

## Interaction outcome

The `INCREASING_SUPPLY` overlap is **confirming rather than contradictory**.

```text
clean SUPPLY_COMING_IN         = 42 events
positive decisive rate         = 54.76%
mean 8-bar return              = +3.61%

SUPPLY_COMING_IN + INCREASING_SUPPLY = 147 events
positive decisive rate                 = 65.31%
mean 8-bar return                      = +3.81%
```

Outcome difference:

```text
positive-rate difference = +10.54 percentage points
mean-return difference    = +0.20 percentage points
```

Therefore:

```text
interaction interpretation = CONFIRMING
interaction penalty        = NONE
rejection                  = NO
```

The overlap must not be mechanically penalized merely because both events describe supply pressure. The outcome evidence indicates that `INCREASING_SUPPLY` commonly strengthens the `SUPPLY_COMING_IN` context.

## Weight sensitivity

Counterfactual weights tested:

```text
0.25, 0.30, 0.38, 0.45, 0.50
```

The frozen candidate population and outcome statistics remained unchanged across tested weights. The test therefore established only score-contribution scaling, not an empirical optimum:

```text
weight 0.25 → relative strength 0.6579
weight 0.30 → relative strength 0.7895
weight 0.38 → relative strength 1.0000
weight 0.45 → relative strength 1.1842
weight 0.50 → relative strength 1.3158
```

A subsequent point-in-time scanner replay confirmed that the tested weights did **not** change qualification or actionability for the 189 frozen events:

```text
qualified events = 189 at every tested weight
actionable events = 56 at every tested weight
actionable rate   = 29.63% at every tested weight
mean actionable return = +2.57% at every tested weight
```

The replay therefore does not justify replacing the dynamic production weighting rule with a fixed empirical weight.

## Production-path readiness

Final production-path audit:

```text
symbols requested                    = 8
symbols with results                 = 8
cheap candidates                     = 1,022
campaign-qualified events            = 370
production emissions                 = 189
expected production emissions        = 189
normal detector rejections           = 181
campaign mismatch                    = 0
expected-event mismatch              = 0
duplicate emissions                  = 0
runtime weight calculator agreement  = 100%
runtime-weight out-of-bounds         = 0
runtime weight observed min          = 0.70
runtime weight observed max          = 1.70
runtime weight observed mean         = 1.0243
interaction penalty configured       = NO
production score mutation            = NO
failures                             = 0
status                               = PASS
```

## Runtime-weight provenance

The runtime weight is calculated by `WeightCalculator._supply_coming_in_weight(ctx)`.

Its production behavior is:

```text
base weight = 1.00
environment adjustment = 0.00
trend adjustment       = context-dependent
structure adjustment   = context-dependent
final clamp             = 0.50–2.00
```

Observed production runtime weights in the audited population were `0.70–1.70`.

Therefore the following concepts remain separate:

```text
registry/profile weight       = 1.00
empirical reference weight    = 0.38
production runtime weight     = dynamic, context-dependent
```

## Frozen production decision

```text
SUPPLY_COMING_IN

production collector     = YES
engine collection         = YES
registry                  = YES
registry weight           = 1.00
runtime weighting         = DYNAMIC
empirical reference       = 0.38
semantic quality          = PASS
interaction penalty       = NONE
rejection rule            = NO
production mutation       = NONE
production-path audit     = PASS
status                    = PRODUCTION-ACTIVE / AUDIT-COMPLETE
```

Future changes to the detector semantics, interaction policy, or weighting strategy must start a new audit cycle rather than bypassing the audit-first process.
