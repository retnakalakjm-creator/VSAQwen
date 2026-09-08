# Evidence Calibration Summary Policy

Milestone 3 calibration work should measure evidence value before changing any
production scanner weights or gates.

## Scope

`audit.calibration` is an analysis-only module. It summarizes rows produced by
`audit.candidates` and must not be imported by production scanner paths to decide
qualification, ranking, actionability, or evidence scores.

The expected flow is:

1. Generate point-in-time scanner candidates.
2. Convert them to candidate outcome rows with `audit.candidates`.
3. Filter to completed scored rows.
4. Summarize by evidence code, qualification, horizon, and side.
5. Review the result before proposing a separate production scoring change.

## Calibration filter

Production calibration should start with completed scored rows only:

```python
from audit.calibration import completed_scored_frame

scored = completed_scored_frame(frame)
```

This keeps two risky cases out of primary calibration:

- latest signals with no execution bar yet;
- partial horizons that have not had enough forward bars.

Exploratory reports may include partial rows with `require_complete=False`, but
those reports must label the sample as partial.

## Evidence-code grouping

Candidate datasets store evidence-code collections as pipe-delimited strings so
CSV exports remain simple:

```text
stopping_volume|no_supply
```

`explode_evidence_codes()` expands those rows so one candidate can contribute to
multiple evidence-code groups. This is useful for ranking which evidence codes
are historically associated with favorable or unfavorable forward outcomes.

## Summary metrics

`summarize_evidence_outcomes()` and `summarize_qualification_outcomes()` report:

- `sample_count`: rows in the group;
- `symbol_count`: distinct symbols represented;
- `actionable_rate`: share of rows marked actionable by the scanner;
- `anomaly_rate`: share of rows whose signal bar was anomalous;
- `win_rate`: share of positive favorable returns;
- `avg_favorable_return`: average direction-adjusted return;
- `median_favorable_return`: median direction-adjusted return;
- `avg_raw_return`: average raw price return;
- `avg_mfe`: average maximum favorable excursion;
- `avg_mae`: average maximum adverse excursion;
- `total_favorable_return`: sum of favorable returns.

## Minimum samples

Use `min_samples` to suppress thin evidence groups:

```python
summary = summarize_evidence_outcomes(frame, min_samples=30)
```

Low sample counts can produce noisy rankings. Do not make production scoring
changes from a tiny group unless the behavior is also supported by domain review
and broader robustness checks.

## Interpretation boundary

A strong calibration group is a research signal, not an automatic production
change. Before modifying scanner weights, verify:

- point-in-time candidate generation is causal;
- outcomes use next-bar execution;
- sample size is adequate;
- results are stable across symbols and time periods;
- anomaly bars are either excluded or reported separately;
- the proposed production change is covered by regression tests.
