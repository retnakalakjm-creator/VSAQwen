# ABSORPTION Audit Record

## Status

`ABSORPTION` is **production-connected / non-scoring / provisional**.

The canonical detector is now connected to the production `EvidenceEngine` through the demand collection path and registered in the evidence registries. It remains excluded from professional scoring and scanner ranking because the audit has not justified a production scoring weight.

```text
base weight        = 0.38   # provisional audit value only
conflict penalty   = 0.20   # provisional audit policy only
production weight  = 0.00
rejection          = NO
production path    = YES
production scoring = NO
```

## Canonical detector

The production detector is:

1. Bearish/down bar.
2. High volume.
3. Above-average spread.
4. Upper close.
5. Lower low than the previous bar.

All five conditions are mandatory. The detector is point-in-time and emits one `EvidenceCode.ABSORPTION` observation on the current bar when the definition passes.

`ABSORPTION` is represented under the dedicated `EvidenceCategory.ABSORPTION` category. Its runtime evidence weight is `0.00`.

## Candidate outcome audit

Original 8-symbol audit:

```text
candidate events              = 68
positive                      = 44
negative                      = 24
flat                          = 0
positive decisive rate        = 64.71%
mean 8-bar return             = +3.08%
failure count                 = 0
```

## Semantic-quality audit

All original candidates satisfied upper-close and lower-low semantics. High-volume and wide-spread classifications were present in `16 / 68` cases each, so those classifications remain supporting descriptors rather than separate mandatory conditions beyond the frozen detector definition.

## Interaction / contradiction audit

Original interaction population:

```text
ABSORPTION candidates                 = 68
INCREASING_SUPPLY_LIKE conflict       = 37
STOPPING_VOLUME_LIKE interaction      = 68
```

The `STOPPING_VOLUME_LIKE` interaction is treated as compatible confirmation. The supply overlap is concentrated entirely in `INCREASING_SUPPLY_LIKE`.

## 30-symbol matched-control robustness

The full robustness audit used 30 symbols, 520 sample bars per symbol, matched target/control events, and 5,000 bootstrap iterations.

### Clean candidates

```text
H=3   pairs=35   delta=+3.503%   95% CI=[+1.018%, +6.143%]   robust positive
H=5   pairs=35   delta=+4.292%   95% CI=[+2.280%, +6.558%]   robust positive
H=10  pairs=35   delta=+5.891%   95% CI=[+3.541%, +8.528%]   robust positive
```

### Conflict candidates

```text
H=3   pairs=37   delta=+0.953%   95% CI=[-0.728%, +2.633%]   inconclusive
H=5   pairs=37   delta=+3.163%   95% CI=[+1.465%, +4.945%]   robust positive
H=10  pairs=37   delta=+1.586%   95% CI=[-0.506%, +3.499%]   inconclusive
```

The conflict group therefore remains positive at H5, but is materially weaker than clean ABSORPTION and is not robust at H3 or H10.

### Leave-one-symbol-out concentration

All 30 symbols remained robustly positive at H3, H5, and H10 when excluded one at a time. The matched-control effect is therefore not dependent on a single symbol.

## Conflict penalty robustness

The clean-minus-conflict delta was:

```text
H=3   penalty=+2.551 pp   95% CI=[-0.477 pp, +5.720 pp]   inconclusive
H=5   penalty=+1.129 pp   95% CI=[-1.603 pp, +3.996 pp]   inconclusive
H=10  penalty=+4.305 pp   95% CI=[+1.242 pp, +7.645 pp]   robust positive
```

This supports a horizon-dependent attenuation effect, strongest and robust at H10, without establishing a universally quantified penalty across every horizon.

## Conflict actionability safety

A counterfactual policy rejecting the `INCREASING_SUPPLY_LIKE` conflict group was evaluated over the 72 matched target events at each horizon.

```text
   H     All    Keep  Reject   PosLost  NegAvoid     MeanAll    MeanKeep      Lift
   3      72      35      37        14        23    -3.143%    -3.244%  -0.101%
   5      72      35      37        17        20    -0.151%     0.280%   0.431%
  10      72      35      37        18        19     1.006%     5.529%   4.524%
```

Conflict outcomes:

```text
   H  Events  Positive  Negative     MeanRet   PosRate
   3      37        14        23    -3.047%   37.84%
   5      37        17        20    -0.559%   45.95%
  10      37        18        19    -3.273%   48.65%
```

Hard rejection is unsafe because it removes meaningful positive outcomes as well as negatives. It slightly worsens H3 mean return and improves H5/H10, with the strongest improvement at H10.

Frozen policy:

```text
hard rejection safety = DO NOT PROMOTE
soft conflict penalty  = RETAIN AS COUNTERFACTUAL / PROVISIONAL
```

The `0.20` penalty remains a research-policy value only. It is not applied by the production scorer.

## Decision-value audit

The original candidate population versus the eligible-market baseline showed:

```text
candidate positive decisive rate = 64.71%
eligible-market positive rate    = 60.68%
positive-rate lift               = +4.02 pp
candidate mean 8-bar return      = +3.08%
eligible-market mean return      = +3.78%
mean-return lift                 = -0.71 pp
candidate share                 = 0.61%
```

This supports retaining ABSORPTION as useful contextual evidence, while not approving a scoring contribution without a genuine production ranking study.

## Production-path integration

The canonical production path now includes:

```text
collector             = YES
dedicated detector     = evidence/absorption.py
collection path       = EvidenceEngine -> collect_demand -> collect_absorption
registry               = YES
category               = ABSORPTION
runtime scoring weight = 0.00
conflict penalty       = 0.20 provisional / not applied
scanner ranking        = UNCHANGED
```

The dedicated category is intentional: it makes the ABSORPTION contribution explicit in the professional scorer rather than silently inheriting a generic effort rule. The canonical scorer can therefore evaluate a counterfactual ABSORPTION weight without changing the production value, which remains `0.00`.

## Production ranking-impact audit

The first genuine production-path counterfactual used the canonical detector and `ScannerEngine.evaluate()` with ABSORPTION weights of `0.00`, `0.10`, `0.15`, `0.20`, `0.25`, `0.30`, and `0.38`.

Production ABSORPTION emissions:

```text
symbols with results = 30
ABSORPTION emissions = 72
```

Counterfactual score impact:

```text
Weight   Mean dStrength   Mean dConfidence   Actionable 0   Actionable 1   Gained   Lost
0.00          0.0000            0.0000              0              0         0       0
0.10          0.0400            0.0200              0              0         0       0
0.15          0.0600            0.0300              0              0         0       0
0.20          0.0800            0.0400              0              0         0       0
0.25          0.1000            0.0500              0              0         0       0
0.30          0.1200            0.0600              0              0         0       0
0.38          0.1520            0.0760              0              0         0       0
```

Interpretation:

- The production scorer now responds to ABSORPTION counterfactual weights, confirming that the scoring path is real rather than a dead configuration entry.
- The response is deterministic and monotonic across the tested weights.
- No ABSORPTION event changed scanner actionability in this population. The event is not part of the scanner's directional VSA confirmation sets, so changing its professional score alone does not make a structural candidate actionable.
- Therefore the tested nonzero weights currently affect the professional score fields but do **not** produce a validated scanner decision/ranking benefit.

Decision from this audit:

```text
counterfactual scoring sensitivity = YES
validated actionability impact      = NO
validated ranking benefit            = NO
production weight                   = KEEP 0.00
```

## Final decision

```text
ABSORPTION
    detector          = PRODUCTION-CONNECTED
    registry          = YES
    base weight       = 0.38   # provisional audit reference
    runtime weight    = 0.00
    conflict penalty  = 0.20   # provisional counterfactual only
    rejection         = NO
    scoring mutation  = NO
    ranking mutation  = NO
    status             = PRODUCTION-CONNECTED / NON-SCORING / PROVISIONAL
```

Future promotion to production scoring requires a validated downstream decision or ranking benefit from the canonical detector, followed by regression validation. No audit-only weight should be interpreted as an active production scoring rule.
