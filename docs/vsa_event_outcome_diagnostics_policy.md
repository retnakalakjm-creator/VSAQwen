# VSA Event Outcome Diagnostics Policy

## Status

Analysis-only diagnostic utility.

This policy documents how to use `audit.vsa_event_diagnostics` when reviewing
VSA event behavior against the Milestone 3 candidate outcome dataset. It does
not change detector logic, scoring weights, ranking, qualification,
actionability, API output, or live scanner behavior.

## Purpose

The VSA event catalog documents what each production or contextual event means.
The candidate outcome dataset records which evidence codes contributed to each
scanner candidate and the forward outcome after next-bar execution.

`audit.vsa_event_diagnostics` connects those layers by producing VSA-focused
summary tables:

- `vsa_event_summary.csv`
- `vsa_event_stability.csv`
- `vsa_event_contracts.csv`
- `vsa_event_metadata.csv`

These files are intended for review before any production calibration PR.

## Evidence columns reviewed

By default, diagnostics inspect all candidate evidence-code columns that may
carry VSA event information:

```text
target_bar_evidence_codes
qualifying_evidence_codes
scoring_evidence_codes
campaign_evidence_codes
```

Codes are normalized to uppercase and matched against `audit.vsa_events`.
Unknown or non-VSA codes are ignored by default.

If the same VSA event appears in more than one evidence column for the same
candidate/horizon row, it is counted once. This prevents a single candidate
from being over-counted just because the event appears in both a target-bar and
scoring evidence field.

## Summary interpretation

`vsa_event_summary.csv` reports grouped outcome statistics by:

```text
vsa_event_code | horizon_bars | side
```

Important columns include:

- `sample_count`
- `symbol_count`
- `win_rate`
- `avg_favorable_return`
- `median_favorable_return`
- `avg_raw_return`
- `avg_mfe`
- `avg_mae`
- `actionable_rate`
- `anomaly_rate`

Contract metadata is joined into the report so each event can be reviewed with
its detector module, detector function, direction, recognition timing, emitted
bar, and future-bar policy.

## Stability interpretation

`vsa_event_stability.csv` applies the same confidence-aware stability logic used
by the calibration bundle. Stability grades are diagnostic labels only:

```text
stable_positive
stable_negative
directionally_positive
directionally_negative
mixed
insufficient_sample
```

A positive or negative stability label is not a production weight change. It is
only evidence that an event deserves deeper review.

## Production calibration boundary

A production event change still requires a separate PR with:

1. event-specific sample review;
2. symbol/diversification review;
3. horizon sensitivity review;
4. interaction/conflict review;
5. tests proving no look-ahead bias;
6. explicit scoring or detector change notes.

Do not change VSA weights from a single diagnostic table alone.

## Example usage

After generating `candidate_outcomes.csv`, use Python or a notebook:

```python
import pandas as pd
from audit.vsa_event_diagnostics import write_vsa_event_diagnostic_bundle

frame = pd.read_csv("reports/calibration/latest/candidate_outcomes.csv")
paths = write_vsa_event_diagnostic_bundle(
    frame,
    "reports/calibration/latest",
    min_samples=30,
    stability_min_samples=30,
)
print(paths.as_dict())
```

For small manual smoke tests, use lower thresholds:

```python
paths = write_vsa_event_diagnostic_bundle(
    frame,
    "reports/calibration/latest",
    min_samples=1,
    stability_min_samples=1,
)
```

## No production behavior change

This utility reads historical candidate outcome rows and writes diagnostic CSVs.
It does not mutate production scanner decisions or persist any state used by the
live scanner.
