# DEMAND_COMING_IN Decision Synthesis

## Status

`DEMAND_COMING_IN` is **production-connected but remains frozen provisional**. The current audit campaign establishes the runtime integration weight and ranking influence. No new replay is authorized unless production semantics, scoring architecture, population contract, an independent validation window, or the counterfactual framework materially changes.

## Existing validated evidence

### Production-path state

- Production path: `YES`.
- Current frozen provisional production/audit weight: `0.38`.
- Observed emitted production weight: `0.38`.
- Registry/profile metadata remains separate from emitted `Evidence.weight`.

### Decision value

- Candidate events: `281` across `8` symbols.
- Candidate positive decisive rate: `66.19%`.
- Eligible-market positive decisive rate: `60.68%`.
- Positive-rate lift: **+5.52 pp**.
- Candidate mean 8-bar forward return: `+4.13%`.
- Eligible-market mean 8-bar forward return: `+3.78%`.
- Mean-return lift: **+0.35 pp**.
- Candidate share of eligible events: `2.51%`.

The event therefore demonstrates useful standalone historical selectivity and a modest return-magnitude advantage, but the effect is not sufficiently stable to justify full production promotion.

### Temporal stability

Chronological decision-value lifts were:

- Window 1: `-7.97 pp`
- Window 2: `+7.07 pp`
- Window 3: `+11.20 pp`
- Window 4: `+20.12 pp`

Three of four windows were positive, with improving later-window behavior. The first negative window and the variability across periods justify retaining provisional status.

### Weighting / production ranking impact

The corrected production ranking-impact audit replayed the canonical production evidence path across the 8-symbol audit universe:

```text
symbols requested      = 8
symbols with results   = 8
target events          = 967
bias changes           = 198
bias change rate       = 20.48%
all emitted weights    = 0.38
failures               = 0
status                 = PASS
```

This establishes that the `0.38` weight is the actual emitted runtime weight and that DCI materially participates in bias/ranking calculation. It does **not** establish that another weight is superior.

The earlier 12/281 final-bias-change replay remains a narrower qualification study and should not be confused with the corrected 967-event production ranking-impact population.

### Final qualification evidence

The earlier focused replay identified `12 / 281` events that changed final bias. Those changed cases showed higher mean return but lower positive rate than unchanged cases and were too small and internally mixed to justify a new production weight or actionability rule.

## Interaction policy

The existing interaction audit did not establish a measurable production conflict penalty:

- `interaction_conflict_penalty = 0.0`.
- No production rejection rule was justified.
- No production qualification change was justified.
- No actionability change was justified.

## Policy decision

### Base weight

Keep `0.38` as a **frozen provisional audit/integration weight**.

Do not promote it to a fully production-approved scoring anchor from the current evidence.

### Conflict penalty

Keep conflict penalty at `0.00`.

No production interaction penalty is authorized by the current evidence.

### Rejection / qualification / actionability

- Rejection rule: **NO**.
- Qualification change: **NO**.
- Actionability change: **NO**.
- Emission semantic change: **NO**.

## Frozen production state

```text
production path        = YES
role                   = primary demand / contextual demand
base audit weight      = 0.38
runtime emitted weight = 0.38
conflict penalty       = 0.00
rejection              = NO
qualification change   = NO
actionability change   = NO
status                 = FROZEN PROVISIONAL
```

## Regression status

The full repository regression suite has passed after the production-policy guards were added:

```text
python -m pytest -q
210 passed
```

This validates the frozen DCI policy boundary but does not authorize a scoring promotion.

## Why no new audit is required now

The candidate, semantic, interaction, temporal, weighting, production integration, ranking-impact, qualification, and regression evidence already establish the current policy. Re-running the same historical population without a material methodological change would not add decision value.

Future review is justified only if:

- production event semantics change;
- professional scoring architecture changes;
- the point-in-time population contract changes;
- a new independent validation window is introduced; or
- the counterfactual framework is materially improved.

## Real-market VSA constraint

The audit deliberately accepts imperfect but meaningful real-market VSA evidence. `DEMAND_COMING_IN` is not required to reproduce textbook-perfect accumulation or demand structure. Its validity rests on confluence of effort, result, volume, spread, close position, subsequent response, and surrounding evidence.

## Final decision

`DEMAND_COMING_IN` remains **FROZEN PROVISIONAL** at `0.38`.

No production promotion, penalty, rejection, qualification change, actionability change, or semantic change is justified from the current evidence. The next change requires new validated evidence or a material change in production semantics/methodology.
