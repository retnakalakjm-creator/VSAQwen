# Calibration Stability Diagnostics Policy

Milestone 3 calibration reports can identify promising or harmful evidence groups, but
raw averages are not enough to justify production scoring changes. Small samples and
symbol concentration can create false confidence. Stability diagnostics are the guardrail
layer between audit reporting and future scoring proposals.

## Purpose

`audit.stability` summarizes completed candidate-outcome rows with confidence-aware
metrics:

- sample count
- symbol count
- positive, negative, and zero outcome counts
- win rate
- Wilson win-rate confidence interval
- average favorable return
- return standard deviation
- standard error of the mean
- approximate average-return confidence interval
- stability grade

These diagnostics are analysis-only. They must not be imported by production scanner
paths to decide actionability, ranking, qualification, or evidence weights.

## Recommended workflow

Generate candidate outcomes and calibration reports first:

```cmd
python -m audit.run_candidate_audit SRF.NS RELIANCE.NS TCS.NS --horizons 1 2 4 8 --output reports/calibration/latest --min-samples 1
```

Then review stability interactively:

```python
import pandas as pd
from audit.stability import summarize_evidence_stability

frame = pd.read_csv("reports/calibration/latest/candidate_outcomes.csv")
stability = summarize_evidence_stability(frame, min_samples=30)
```

## Stability grades

The default labels are intentionally conservative:

- `stable_positive`: sample count passes the threshold, the average favorable-return
  confidence interval is above zero, and the Wilson win-rate lower bound is above 50%.
- `stable_negative`: sample count passes the threshold, the average favorable-return
  confidence interval is below zero, and the Wilson win-rate upper bound is below 50%.
- `directionally_positive`: average return and win rate are positive, but the confidence
  intervals are not strong enough for a stable label.
- `directionally_negative`: average return and win rate are negative, but the confidence
  intervals are not strong enough for a stable label.
- `mixed`: evidence is inconclusive.
- `insufficient_sample`: sample count is below the selected minimum.

## Interpretation rules

Use stability diagnostics as a review filter, not as an automatic optimizer.

A future production weight change should require at least:

1. Sufficient samples across multiple symbols.
2. Consistency across more than one horizon.
3. No obvious concentration in one ticker, regime, or short time window.
4. Review of anomaly flags and partial-horizon exclusions.
5. A separate PR that changes production scoring only after the evidence is reviewed.

## Approximation notes

The win-rate interval uses Wilson score bounds. The favorable-return interval uses a
normal approximation around the sample mean. This is suitable as a lightweight screening
signal, not a substitute for a full walk-forward or regime-split validation.

## Production boundary

`audit.stability` is part of the audit package. Production scanner modules must not use
these outputs at runtime. Stability reports are evidence for human review and follow-up
experiments only.
