# Offline Point-in-Time Daily Evidence Producer

## Purpose

K5 supplies the genuine daily-evidence source required after K4.

It does so by reusing the existing ProVSA detector stack offline on completed
daily bars. It does not reinterpret weekly artifacts and does not introduce a
second daily VSA detector.

## Reused stack

For each completed daily target bar, K5 runs:

```text
raw completed daily prefix
        ↓
MetricsEngine
        ↓
SwingEngine
        ↓
StructureFilter
        ↓
TrendAnalyzer
        ↓
EvidenceEngine
        ↓
Evidence whose bar_index == current daily target
```

These are the same domain components used by the production scanner pipeline.

K5 deliberately does not call ScannerEngine qualification, professional
candidate ranking/actionability, alerts, or execution.

## Explicit prefix replay

For target bar N, the evaluator receives only:

```text
daily bars 0 ... N
```

The future suffix is never passed to the detector stack.

Metrics are recomputed from each raw prefix in this first research cut. This is
slower than a cached full-frame calculation but makes the causal boundary
explicit and independent of assumptions about future metric implementations.

## Completed sessions only

K5 first applies `completed_daily_only()`.

Therefore:

- a forming current-session daily candle is excluded;
- non-session dates are excluded according to the supplied TradingCalendar;
- all retained evidence comes from completed daily bars.

## Legacy evidence date field

The current Evidence model names its date identity field `week_beginning`.

K5 does not change that production model. Inside the offline daily producer the
same field carries the exact completed **daily session identity** used for the
metrics prefix.

That is a compatibility bridge, not a claim that the evidence is weekly.

## Target-bar retention

EvidenceEngine may use older bars as context.

K5 retains only evidence where:

```text
evidence.bar_index == current target bar_index
```

Older evidence is not duplicated or re-attributed to later daily bars.

An injected prefix evaluator that returns evidence for another bar is rejected.

## Source fingerprint

K5 fingerprints the exact completed raw input consumed by the producer:

- normalized symbol;
- session identity;
- open;
- high;
- low;
- close;
- volume.

Changing any consumed OHLCV value changes the source fingerprint.

## K4 handoff

K5 produces:

- completed daily bars;
- point-in-time target-bar Evidence;
- source fingerprint.

A later preparation step can combine that archive with independently causal
weekly-direction assignments and freeze the result through the K4 dataset
contract.

K5 does **not** infer the weekly direction.

## Safety boundary

K5 is analysis-only.

It does not:

- run weekly qualification on daily bars;
- create a daily qualification;
- create a scanner candidate;
- create a daily score or ranking;
- change F3 fresh-signal behavior;
- change K1/K2/K3/K4 semantics;
- alter production actionability;
- generate alerts or orders.

The output is a research evidence source, not an entry recommendation.
