# INCREASING_DEMAND Decision Synthesis

## Status

`INCREASING_DEMAND` is **production-connected but remains provisional**. No new audit replay is authorized unless production semantics, scoring architecture, or the frozen population contract changes.

## Existing validated evidence

### Production-path state

- Production path: YES.
- Production emissions observed: `905`.
- Symbols with production hits: `8 / 8`.
- Observed emitted runtime weight: `[0.85]`.
- Current professional scoring-map/base weight: `0.85`.

### Calibration evidence

- Calibration population: `902` events across 8 symbols.
- Beneficial decision changes: `26`.
- Harmful decision changes: `15`.
- Net benefit: `+11`.
- Benefit/harm ratio: `1.7333`.
- Leave-one-symbol-out minimum net benefit: `+6`.

The leave-one-symbol-out result is positive across every held-out symbol, which supports robustness of the observed scoring benefit.

### Conflict evidence

- Conflict events: `41 / 902`.
- Conflict rate: `4.55%`.
- Hidden-supply-like conflicts: `41`.
- Buying-climax-like conflicts: `16`.
- Upthrust-like conflicts: `1`.
- Supply-coming-in-like conflicts: `0`.
- Increasing-supply-like conflicts: `0`.
- No-demand-like conflicts: `0`.

Conflict outcomes:

- Usable events: `899`.
- Conflict events: `41`.
- Clean events: `858`.
- Conflict mean return: `+0.72%`.
- Clean mean return: `+3.83%`.
- Conflict return gap: `-3.11 pp`.
- Conflict positive rate: `51.22%`.
- Clean positive rate: `59.44%`.
- Positive-rate gap: `-8.22 pp`.

The conflict population therefore contains a materially weaker outcome profile than the clean population.

## Policy decision

### Base weight

Keep the current `0.85` base scoring weight **provisional**.

Reason: the existing calibration evidence is encouraging and robust, but the project has not frozen a final production policy that converts this event into a fully production-approved scoring anchor.

### Conflict penalty

The audited `0.10` conflict penalty remains **provisional / study-only**.

Do **not** activate it in production yet.

Reason:

- The historical degradation is real and substantial.
- However, the evidence demonstrates an interaction relationship, not definitive causal superiority of the exact `0.10` penalty.
- Activating the penalty would be a production scoring-policy change and must be supported by a frozen counterfactual decision-value comparison at the production scoring layer.
- The current architecture explicitly separates audit conclusions from active production rules.

### Rejection / qualification / actionability

- Rejection rule: **NO**.
- Qualification change: **NO**.
- Actionability change: **NO**.
- Emission semantics change: **NO**.

## Frozen production state

```text
production path       = YES
runtime weight        = 0.85
base scoring weight   = 0.85
conflict penalty      = 0.10 provisional / NOT ACTIVE
rejection             = NO
qualification change  = NO
actionability change  = NO
status                = PROVISIONAL
```

## Why no new audit is required now

The candidate, semantic, interaction, conflict, calibration, and leave-one-symbol-out evidence already exists. Re-running those audits without a code or contract change would only reproduce the same frozen evidence and increase runtime without adding decision value.

Future review is justified only if:

- production event semantics change;
- the professional scoring formula changes;
- the event's population contract changes;
- a new independent validation window is introduced; or
- a production-layer counterfactual framework is materially improved.
