# Calibration Report Export Policy

Milestone 3 calibration reports are analysis-only artifacts. They help review
which evidence groups have historically shown favorable or unfavorable forward
outcomes before any production scoring changes are proposed.

## Standard report bundle

`audit.reports.write_calibration_report_bundle()` writes these CSV files:

- `evidence_summary.csv`
- `qualification_summary.csv`
- `top_positive_evidence.csv`
- `bottom_negative_evidence.csv`
- `metadata.csv`

The source input is a candidate outcome DataFrame produced by `audit.candidates`.
The summary calculations use `audit.calibration` and therefore preserve the
same completed scored-row boundary.

## Recommended destination

Generated report files should be written outside the committed source tree or to
an ignored analysis output folder, for example:

```cmd
python your_audit_script.py --output reports\calibration\latest
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
8. whether results persist across symbols and periods.

Small-sample groups should be treated as leads for further investigation, not as
proof that a VSA rule is good or bad.

## Production boundary

The report export module must not be imported by production scanner paths to
change qualification, actionability, ranking, or scoring.

A safe workflow is:

1. build candidate outcome rows;
2. summarize evidence and qualification outcomes;
3. export the report bundle;
4. manually review results;
5. propose production scoring changes in a separate PR, with tests and rationale.
