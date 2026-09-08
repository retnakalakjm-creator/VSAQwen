# Milestone 4 Calibration Proposal Policy

## Status

Milestone 4 starts with a proposal layer, not direct production scoring changes.

The goal is to convert Milestone 3 audit outputs into reviewable, deterministic CSVs that identify which evidence or VSA event groups deserve human review for future strategy changes.

## Boundary

`audit.proposals` is analysis-only. It must not:

- change detector logic;
- change scoring weights;
- change scanner thresholds;
- change ranking, qualification, or actionability;
- change API or live scanner behavior;
- write production configuration files.

Any production strategy update must happen in a later explicit PR with the supporting proposal rows cited in the PR body.

## Inputs

The proposal layer is designed for summary outputs such as:

```text
reports\calibration\latest\evidence_summary.csv
reports\calibration\latest\evidence_stability.csv
reports\calibration\latest\vsa_event_summary.csv
reports\calibration\latest\vsa_event_stability.csv
```

The required summary columns are:

```text
group_key
sample_count
symbol_count
horizon_bars
side
win_rate
avg_favorable_return
total_favorable_return
anomaly_rate
```

If stability evidence is supplied, it must include:

```text
group_key
stability_grade
```

Confidence interval columns such as `favorable_return_ci_low` and `favorable_return_ci_high` are carried through when available.

## Proposal actions

The default actions are:

```text
review_for_weight_increase
review_for_weight_decrease
review_for_monitoring
collect_more_data
keep_current
```

These are recommendations for review only. They are not executable strategy changes.

## Default gates

The default criteria require:

```text
min_samples = 30
min_symbols = 5
min_win_rate = 0.52
max_negative_win_rate = 0.48
min_avg_favorable_return = 0.0
max_negative_avg_favorable_return = 0.0
max_anomaly_rate = 0.25
require_stability = True
```

A group with weak sample size, weak symbol coverage, excessive anomaly rate, or insufficient stability is routed to `collect_more_data`.

## Example usage

```python
import pandas as pd
from audit.proposals import CalibrationProposalCriteria, write_calibration_proposal_bundle

summary = pd.read_csv("reports/calibration/latest/evidence_summary.csv")
stability = pd.read_csv("reports/calibration/latest/evidence_stability.csv")

paths = write_calibration_proposal_bundle(
    summary,
    "reports/calibration/latest",
    stability=stability,
    criteria=CalibrationProposalCriteria(min_samples=30, min_symbols=5),
    source="evidence_summary",
)
print(paths.as_dict())
```

For exploratory review only, stability can be relaxed:

```python
CalibrationProposalCriteria(require_stability=False)
```

That must not be used as the sole basis for a production scoring PR.

## Recommended Milestone 4 workflow

1. Generate a broad candidate outcome dataset across enough symbols and history.
2. Generate calibration, stability, and VSA event summaries.
3. Generate proposal CSVs from the summaries.
4. Review only `review_for_*` rows with enough sample and symbol coverage.
5. Create a separate production PR for any specific scoring or threshold change.
6. Rerun the historical audit after the production change and compare before/after results.
