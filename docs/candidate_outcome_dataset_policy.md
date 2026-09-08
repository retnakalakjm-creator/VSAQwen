# Candidate Outcome Dataset Policy

Milestone 3 uses candidate-level outcome datasets to measure whether scanner
qualifications and evidence groups have forward value before changing production
weights or gates.

## Scope

`audit.candidates` is analysis-only. It converts already-generated scanner
candidates into flat rows and joins each candidate to one or more forward
outcome horizons from `audit.outcomes`.

It must not be imported by production scanner paths to decide:

- actionability;
- qualification;
- ranking;
- evidence weights;
- live scanner output filtering.

## Row model

Each row represents one candidate observation and one requested horizon.

Important columns include:

- `candidate_id`;
- `symbol`;
- `signal_bar_index` and `signal_week`;
- `execution_bar_index` and `execution_week` from the candidate;
- `outcome_execution_bar_index` from the outcome calculation;
- `qualification`;
- `side`;
- `actionable`;
- `confidence`, `net_strength`, `net_pressure`;
- target, qualifying, scoring, and campaign evidence code strings;
- `raw_return`, `favorable_return`, `mfe`, `mae`;
- `outcome_available`;
- `complete`.

Evidence-code collections are pipe-delimited strings so the output is directly
CSV-friendly while remaining easy to split during analysis.

## Direction handling

The default side resolver maps:

- `persistent_bullish` to `long`;
- `persistent_bearish` to `short`;
- `unqualified` to `neutral`.

Callers can provide a custom `side_resolver` when auditing a specific evidence
family or hypothesis.

## Latest and partial observations

Latest candidates with no following execution bar are retained by default with
`outcome_available=False`. This preserves the observation but prevents accidental
same-bar scoring.

For production calibration, use rows where:

```python
frame[frame["outcome_available"] & frame["complete"]]
```

Exploratory reports may include partial horizons only if the report clearly
labels that choice.

## Example

```python
from audit.candidates import build_candidate_outcome_frame
from scanner import ScannerEngine

candidates = ScannerEngine().scan(metrics)
frame = build_candidate_outcome_frame(
    metrics,
    candidates,
    horizons=[1, 4, 8, 12],
    symbol="SRF.NS",
)
calibration_frame = frame[frame["outcome_available"] & frame["complete"]]
```

## Next step

After candidate datasets are generated consistently, future Milestone 3 work can
aggregate by evidence code, qualification, trend state, anomaly flag, and horizon
to decide which signals deserve stronger, weaker, or disabled scoring treatment.
