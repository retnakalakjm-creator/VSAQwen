# Calibration Report Export Policy

Milestone 3 calibration reports are analysis-only artifacts. They help review
which evidence groups have historically shown favorable or unfavorable forward
outcomes before any production scoring changes are proposed.

## Standard report bundle

`audit.reports.write_calibration_report_bundle()` writes these CSV files by
default:

- `evidence_summary.csv`
- `qualification_summary.csv`
- `top_positive_evidence.csv`
- `bottom_negative_evidence.csv`
- `evidence_stability.csv`
- `top_stable_positive_evidence.csv`
- `top_stable_negative_evidence.csv`
- `metadata.csv`

The source input is a candidate outcome DataFrame produced by `audit.candidates`.
The summary calculations use `audit.calibration` and `audit.stability`, and they
therefore preserve the same completed scored-row boundary.

Set `include_stability=False` when a caller intentionally wants only the older
calibration summary files.

## Stability files

The stability files add confidence-aware diagnostics to the raw calibration
summary:

- `evidence_stability.csv` contains Wilson win-rate confidence intervals,
  favorable-return confidence bands, and the `stability_grade` label for each
  evidence/horizon/side group.
- `top_stable_positive_evidence.csv` contains positive stability grades sorted
  by favorable-return confidence support.
- `top_stable_negative_evidence.csv` contains negative stability grades sorted
  by unfavorable confidence support.

The stable-positive and stable-negative files are review aids. They are not an
automatic instruction to increase or decrease evidence weights.

## Recommended destination

Generated report files should be written outside the committed source tree or to
an ignored analysis output folder, for example:

```cmd
python -m audit.run_candidate_audit SRF.NS RELIANCE.NS TCS.NS --output reports\calibration\latest
```

Do not commit generated calibration CSVs unless they are small, intentional test
fixtures. Historical calibration outputs can become stale quickly as the scanner,
data vendor output, or candidate rules evolve.

## Interpretation rules

Use report rows as evidence for review, not as automatic production changes.
Before changing weights or gates, review:

1. sample count;
2. symbol count;
3. horizon and side;
4. anomaly rate;
5. win rate;
6. average and median favorable return;
7. MFE and MAE profile;
8. confidence intervals and stability grade;
9. whether results persist across symbols and periods.

Small-sample groups should be treated as leads for further investigation, not as
proof that a VSA rule is good or bad.

## Production boundary

The report export module must not be imported by production scanner paths to
change qualification, actionability, ranking, or scoring.

A safe workflow is:

1. build candidate outcome rows;
2. summarize evidence and qualification outcomes;
3. export the report bundle;
4. review calibration and stability outputs;
5. propose production scoring changes in a separate PR, with tests and rationale.
