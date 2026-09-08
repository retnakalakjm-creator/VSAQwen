# Historical candidate audit runner policy

Milestone 3 uses historical outcome audits to evaluate whether scanner evidence
is actually useful before changing production evidence weights or qualification
rules.

## Purpose

`audit.runner` connects the existing full-replay scanner path to the analysis
utilities added earlier in Milestone 3:

1. load daily OHLCV data,
2. convert daily bars to completed weekly bars,
3. calculate weekly metrics,
4. run `ScannerEngine().scan(metrics)` point-in-time,
5. build candidate outcome rows with `audit.candidates`,
6. optionally write `candidate_outcomes.csv`, and
7. optionally write the calibration CSV report bundle from `audit.reports`.

The runner is analysis-only. It must not change production scanner scoring,
actionability, qualification, ranking, API responses, or live scanner behavior.

## CLI usage

```cmd
python -m audit.run_candidate_audit SRF.NS RELIANCE.NS TCS.NS --horizons 1 2 4 8 --output reports/calibration/latest
```

The default output directory is:

```text
reports/calibration/latest
```

The default horizons are:

```text
1, 2, 4, 8 bars after the execution bar
```

## Output files

When dataset and report writing are enabled, the output directory contains:

```text
candidate_outcomes.csv
metadata.csv
evidence_summary.csv
qualification_summary.csv
top_positive_evidence.csv
bottom_negative_evidence.csv
```

`candidate_outcomes.csv` is the primary raw audit artifact. The other files are
summary views for calibration review.

## Execution timing

The runner inherits the Milestone 3 execution rule from `audit.outcomes`:

- signal observed on bar `N`,
- execution modeled from bar `N + 1`,
- never score same-bar execution,
- latest signals without an execution bar are retained as unscored rows by
  default.

Use `--drop-unscored` when a report should exclude latest unscored candidates
from the raw dataset as well as from completed-row summaries.

## Calibration boundary

This runner creates evidence for decision making; it does not make the decision.

Before changing production weights or disabling evidence rules:

1. run the audit across enough symbols and history,
2. filter to completed scored rows,
3. require enough samples per evidence group,
4. compare multiple horizons,
5. inspect raw rows for data-quality or corporate-action anomalies, and
6. create a separate production calibration PR.

Do not treat a small positive or negative average return from one run as proof
that a VSA concept works or fails.

## Testing policy

Unit tests for the runner use injected synthetic loaders, transformers, metrics
calculators, and scanners. They must not call yfinance or depend on live network
data.

The real CLI command is an integration/research workflow and should be run
manually when calibration data is needed.
