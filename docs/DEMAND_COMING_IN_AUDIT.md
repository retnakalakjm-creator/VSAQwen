# DEMAND_COMING_IN Audit

This is an audit-only record of the `DEMAND_COMING_IN` evidence event. It records the completed semantic, interaction, decision-value, temporal, weighting, integration, and qualification audits. It does not authorize a production promotion beyond the stated provisional weight.

## Current status

`DEMAND_COMING_IN`

- Role: Primary demand
- Direction: Bullish
- Status: **Provisional**
- Production weight: **0.38**
- Production actionability: **NO PROMOTION**
- Current detector path: `evidence/demand.py`
- Weight path: helper-level evidence construction; `WeightCalculator` remains unchanged

## Semantic audit

The historical candidate population contained `281` events across `8` symbols.

Semantic quality:

- `240 / 281` semantic-quality-like events
- Semantic-quality-like rate: `85.41%`
- Positive decisive rate: `66.19%`
- Volume increasing: `217`
- Higher low: `47`
- Both supporting: `24`
- Non-climactic: `281`

The candidate definition was accepted as meaningful real-market demand evidence without requiring textbook-perfect VSA structure.

## Interaction / contradiction audit

The interaction audit did not establish a production rejection rule or a measurable conflict penalty against `DEMAND_COMING_IN`.

`interaction_conflict_penalty = 0.0` in the final weighting audit.

Therefore no additional contradiction penalty was introduced.

## Decision-value audit

Across `281` candidate events:

- Candidate positive decisive rate: `66.19%`
- Eligible-market positive decisive rate: `60.68%`
- Decision-value lift: **+5.52 percentage points**
- Candidate share of eligible events: `2.51%`

The lift is positive overall but varies by symbol. It was therefore treated as useful evidence rather than a universally strong standalone signal.

## Temporal stability audit

Chronological decision-value lifts were:

- Window 1: `-7.97 pp`
- Window 2: `+7.07 pp`
- Window 3: `+11.20 pp`
- Window 4: `+20.12 pp`

Three of four windows were positive. The improving later-window behavior is encouraging, but the historical instability is sufficient to keep the event provisional.

## Return-magnitude audit

Mean 8-bar forward return:

- Candidate: `4.13%`
- Eligible market: `3.78%`
- Mean-return lift: **+0.35 percentage points**

The return-magnitude advantage is modest and inconsistent across symbols. It supports usefulness but does not justify a strong standalone contribution.

## Weighting audit

The combined audit produced:

- Normalized audit score: `0.6316`
- Provisional range: `0.25 - 0.50`
- Recommended audit weight: **0.38**
- Production weight before audit: `0.00`
- Production action: **DO NOT REGISTER YET**

Weight sensitivity remained controlled across `0.25`, `0.30`, `0.38`, `0.45`, and `0.50`. The selected `0.38` weight was retained rather than increased.

## Production-path integration

The production replay confirmed:

- Candidate bars replayed for the path audit: `49`
- Actual production hits: `49`
- Collector contains target: `YES`
- Demand collection is wired through `EvidenceEngine.collect()`
- Emitted production weights observed: `[0.38]`
- All audited target events were weighted at `0.38`

The registry profile remains `1.00 / 0.90` as profile metadata; it is not the emitted `Evidence.weight` for this event.

## Regression and ranking audit

Full regression:

- Target events: `281`
- Weighted at `0.38`: `281`
- Weight integrity: `TRUE`
- Failures: `0`

Optimized ranking-impact replay:

- Target events: `281`
- Bias changes caused by the target contribution: `12`
- Bias-change rate: **4.27%**
- All target weights: `0.38`
- Failures: `0`

The effect is controlled rather than dominant. The event can change the final bias in a small minority of cases.

## Final qualification audit

Only the `12` bias-changing events were compared with the `269` unchanged events using the same 8-bar forward-return horizon.

Bias-changing events:

- Mean return: `7.49%`
- Positive rate: `58.33%`

Bias-unchanged events:

- Mean return: `3.98%`
- Positive rate: `66.54%`

Differences:

- Mean-return delta: **+3.52 percentage points**
- Positive-rate delta: **-8.21 percentage points**

The changed-decision sample is very small and has conflicting evidence: better average magnitude but worse positive-hit rate. This does not justify production promotion or further weight tuning from the current sample.

## Final decision

`DEMAND_COMING_IN` is accepted as a **real-market contextual demand event** with a frozen **provisional audit weight of 0.38**.

It remains:

- production-collected;
- production-weighted at `0.38` for audit/integration purposes;
- **not promoted to fully validated production actionability**;
- not subject to another weight-tuning cycle from this sample.

## Real-market VSA constraint

The audit intentionally accepts imperfect but meaningful real-market VSA evidence. The event is not required to reproduce a textbook-perfect accumulation or demand sequence. Its validity rests on the quality and confluence of effort, result, volume, spread, close position, subsequent response, and interaction with surrounding evidence.

## Next step

Freeze the `DEMAND_COMING_IN` result and move to the next provisional evidence event rather than continuing to optimize this event from the same historical sample.
