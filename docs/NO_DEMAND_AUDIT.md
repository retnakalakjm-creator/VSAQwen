# NO_DEMAND Audit Record

## Final status

`NO_DEMAND` is production-active and audit-complete for the current detector and scoring architecture. The audit established the event's candidate quality, semantic integrity, interaction behavior, decision-value characteristics, weight sensitivity, and production-path readiness without changing production detector semantics.

```text
production path                 = YES
collector                       = evidence/demand.py::_collect_no_demand
engine collection               = YES (via collect_demand)
category                        = Supply
VSA direction                   = Bearish
registry/profile weight         = 1.00
configured supply-map weight    = 0.60
runtime Evidence.weight model   = dynamic WeightCalculator
runtime observed range          = 0.70–1.50
production interaction penalty = NONE
production status               = ACTIVE / AUDIT-COMPLETE
```

The registry/reference weight, configured scoring-map weight, and dynamic emission weight are three separate concepts. They must not be forced to match.

## Audit completion

The event completed the current audit-first validation sequence:

1. Candidate audit — PASS
2. Semantic-quality audit — PASS
3. Interaction / contradiction audit — PASS
4. Interaction outcome audit — PASS
5. Decision-value audit — PASS
6. Weight-sensitivity audit — PASS
7. Production-path readiness audit — PASS after correcting the audit contract for dynamic runtime weights

The weight-sensitivity audit was optimized so the expensive point-in-time target replay is prepared once and the counterfactual weight loop changes only the live scoring-map configuration used by `ProfessionalScoringEngine`.

## Frozen candidate population

Across the 8-symbol audit universe:

```text
symbols requested             = 8
symbols with results          = 8
cheap candidates              = 202
candidate events              = 109
expected candidate events     = 109
normal detector rejections    = 93
```

The 109-event candidate population is frozen for downstream audits.

## Detector semantics

The validated production detector uses four mandatory requirements:

1. Bullish Environment
2. Bullish Bar
3. Low Volume
4. Narrow Spread

The detector also evaluates two optional confirmations:

1. Volume Decreasing
2. Weak Close

The confirmations are **not mandatory emission requirements**. The semantic audit therefore treats them as quality evidence and reports their frequency separately.

Semantic-quality audit:

```text
bullish_environment          = 109 / 109
bullish_bar                  = 109 / 109
low_volume                   = 109 / 109
narrow_spread                = 109 / 109
volume_decreasing            = 79 / 109 confirmation
weak_close                   = 12 / 109 confirmation
mandatory semantic failures  = 0
duplicate emissions          = 0
target-bar-only              = YES
point-in-time                = YES
production context used      = YES
production emission authority = YES
```

Detector semantics were not tightened to require textbook-perfect confirmations. Real-market VSA evidence remains admissible when the mandatory production requirements are satisfied.

## Outcome / decision-value audit

Using the project's 8-bar forward-return methodology:

```text
candidate events              = 109
positive outcomes             = 69
negative outcomes             = 40
flat outcomes                 = 0
decisive outcomes             = 109
positive decisive rate        = 63.30%
mean 8-bar return             = +3.62%
```

Eligible-market comparison:

```text
eligible market events        = 11,345
eligible positive decisive rate = 60.79%
candidate rate lift            = +2.51 percentage points
eligible mean return           = +3.83%
candidate mean-return lift     = -0.21 percentage points
candidate share of eligible    = 0.96%
```

Conclusion: `NO_DEMAND` demonstrates modest incremental **directional classification value** (+2.51 pp positive-decisive-rate lift) but not incremental **return magnitude** in this audit population (-0.21 pp mean-return lift).

Because the candidate population is only 0.96% of eligible market events, these results do not justify changing production weight on decision-value evidence alone.

## Interaction / contradiction audit

The frozen 109-event population produced:

```text
events with interaction        = 1
events with supply interaction = 0
events with demand interaction = 1
interaction rate               = 0.917%
self-conflict excluded         = YES
target-bar-only                = YES
point-in-time                  = YES
production context used        = YES
duplicate emissions            = 0
status                         = PASS
```

The only interaction was:

```text
NO_DEMAND + SHAKEOUT = 1 event
```

No supply-side contradiction was observed.

## Interaction outcome

The outcome groups were:

| Group | Events | Positive decisive rate | Mean 8-bar return |
|---|---:|---:|---:|
| Clean | 108 | 62.96% | +3.57% |
| `NO_DEMAND + SHAKEOUT` | 1 | 100.00% | +9.21% |

The single `SHAKEOUT` overlap had a stronger observed outcome than the clean group, but `n=1` is far too small to justify any interaction adjustment.

Frozen interaction policy:

```text
interaction penalty = NONE
rejection rule      = NO
```

## Weight-sensitivity audit

Counterfactual scoring weights tested:

```text
0.40, 0.50, 0.60, 0.70, 0.80, 1.00
```

Reference / current configured scoring weight:

```text
0.60
```

The optimized replay established that the live scoring-map weight genuinely reaches the professional scoring path.

| Weight | Score changes vs 0.60 | Rank positions changed vs 0.60 | Mean supply score | Mean net strength |
|---:|---:|---:|---:|---:|
| 0.40 | 30 / 109 | 81 / 109 | 0.8422 | -0.3401 |
| 0.50 | 28 / 109 | 65 / 109 | 0.8716 | -0.3519 |
| **0.60** | **0 / 109** | **0 / 109** | **0.8972** | **-0.3621** |
| 0.70 | 28 / 109 | 69 / 109 | 0.9229 | -0.3724 |
| 0.80 | 28 / 109 | 87 / 109 | 0.9486 | -0.3827 |
| 1.00 | 28 / 109 | 108 / 109 | 1.0000 | -0.4032 |

Qualification/actionability were not replayed in this audit because their semantics are weight-independent and were already validated by separate audits.

Conclusion:

```text
weight affects professional scoring = YES
weight affects confidence          = YES
weight affects ranking             = YES
qualification impact               = NOT REPLAYED HERE
actionability impact               = NOT REPLAYED HERE
```

## Production-path readiness

The corrected production readiness audit established:

```text
cheap candidates                  = 202
production emissions              = 109
expected emissions                = 109
registry weight                   = 1.00
configured scoring-map weight     = 0.60
runtime weight model               = dynamic WeightCalculator
runtime observed min               = 0.70
runtime observed max               = 1.50
runtime observed mean              = 1.2083
runtime bounds                     = 0.50–2.00
runtime within bounds              = YES
runtime/config equality required   = NO
registry/config discrepancy        = YES
duplicate emissions               = 0
provenance failures                = 0
production score mutation          = NO
point-in-time                     = YES
status                             = PASS
```

The apparent discrepancy between runtime `Evidence.weight` and the configured `SUPPLY_EVIDENCE_WEIGHTS[NO_DEMAND]` is not a production failure. `Evidence.weight` is generated by the context-dependent `WeightCalculator`, while `ProfessionalScoringEngine` uses the separate live scoring-map weight for professional supply scoring.

## Frozen production decision

```text
NO_DEMAND

production collector              = YES
production emission               = YES
registry/reference weight         = 1.00
configured scoring weight         = 0.60
dynamic runtime Evidence.weight   = 0.70–1.50 observed
interaction penalty               = NONE
rejection rule                    = NO
semantic mandatory failures       = 0
qualification change              = NONE observed in separate validation
actionability change              = NONE observed in separate validation
ranking / strength sensitivity    = YES
production weight change          = NONE
status                            = PRODUCTION-ACTIVE / AUDIT-COMPLETE
```

The current audit campaign does **not** justify changing the production scoring weight away from `0.60`, nor does it justify forcing dynamic emitted weights to equal the scoring-map value.

## Audit principles preserved

- Real-market VSA evidence may be imperfect; textbook purity is not required.
- Mandatory detector semantics remain unchanged during calibration.
- Optional confirmations are reported as quality evidence, not promoted to hard requirements.
- Weight tuning changes professional scoring only; it does not change event detection.
- Interaction overlap is not automatically a contradiction.
- Dynamic emission weights and static scoring-map weights are separate concepts.
- Production-path audits must validate the actual runtime contract rather than assuming registry/config/runtime values are identical.
