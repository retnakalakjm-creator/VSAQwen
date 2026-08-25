# DEMAND_COMING_IN Decision Synthesis

## Status

`DEMAND_COMING_IN` is **production-connected but remains provisional**. The existing audit campaign is frozen; no new replay is authorized unless the production semantics, scoring architecture, population contract, independent validation window, or counterfactual framework materially changes.

## Existing validated evidence

### Production-path state

- Production path: `YES`.
- Current provisional production/audit weight: `0.38`.
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

### Weighting / ranking impact

- Normalized audit score: `0.6316`.
- Recommended provisional weight: **`0.38`**.
- Tested sensitivity range: `0.25`, `0.30`, `0.38`, `0.45`, `0.50`.
- Production integration replay: `49 / 49` target bars emitted at `0.38`.
- Full regression weight integrity: `TRUE`.
- Ranking-impact replay: `12 / 281` events changed final bias (`4.27%`).

The event has controlled ranking influence rather than dominant influence.

### Final qualification evidence

For the 12 bias-changing events versus 269 unchanged events:

- Bias-changing mean return: `+7.49%`.
- Bias-changing positive rate: `58.33%`.
- Unchanged mean return: `+3.98%`.
- Unchanged positive rate: `66.54%`.
- Mean-return delta: **+3.52 pp**.
- Positive-rate delta: **-8.21 pp**.

The changed-decision sample is too small and internally mixed: higher magnitude but lower hit rate. It does not justify promotion or another weight-tuning cycle on the same sample.

## Interaction policy

The existing interaction audit did not establish a measurable production conflict penalty:

- `interaction_conflict_penalty = 0.0`.
- No production rejection rule was justified.
- No production qualification change was justified.
- No actionability change was justified.

## Policy decision

### Base weight

Keep `0.38` as a **frozen provisional audit/integration weight**.

Do not promote it to a fully production-approved scoring anchor from the current historical sample.

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
production path       = YES
role                  = primary demand / contextual demand
base audit weight     = 0.38
runtime emitted weight= 0.38
conflict penalty      = 0.00
rejection             = NO
qualification change  = NO
actionability change  = NO
status                = PROVISIONAL
```

## Why no new audit is required now

The candidate, semantic, interaction, temporal, weighting, integration, regression, ranking-impact, and final-qualification evidence already exists. Re-running the same audit against the same historical population would reproduce the same evidence without adding decision value.

Future review is justified only if:

- production event semantics change;
- professional scoring architecture changes;
- the point-in-time population contract changes;
- a new independent validation window is introduced; or
- the counterfactual framework is materially improved.

## Real-market VSA constraint

The audit deliberately accepts imperfect but meaningful real-market VSA evidence. `DEMAND_COMING_IN` is not required to reproduce textbook-perfect accumulation or demand structure. Its validity rests on confluence of effort, result, volume, spread, close position, subsequent response, and surrounding evidence.

## Final decision

`DEMAND_COMING_IN` remains **PROVISIONAL** at `0.38`.

No production promotion, penalty, rejection, qualification change, actionability change, or semantic change is justified from the current sample.
