# Audit Runner CLI Policy

## Status

Operational documentation for the analysis-only historical candidate audit runner.

The audit runner builds `candidate_outcomes.csv`, calibration report CSVs, and VSA event diagnostic CSVs. It does not change production scanner decisions, detector logic, scoring, ranking, qualification, actionability, API output, or live scanner behavior.

## Supported entrypoints

From the repository root, both invocation styles are supported:

```cmd
python -m audit.run_candidate_audit SRF.NS RELIANCE.NS TCS.NS --output reports\calibration\latest
```

```cmd
python audit\run_candidate_audit.py SRF.NS RELIANCE.NS TCS.NS --output reports\calibration\latest
```

The module form is still preferred for package-style execution. The script-path form is supported because it is common on Windows Command Prompt and avoids confusion when users copy paths from the repository tree.

## Output

The default dataset path is:

```text
reports\calibration\latest\candidate_outcomes.csv
```

When reports are enabled, the runner writes the standard calibration files to the same output directory:

```text
reports\calibration\latest\evidence_summary.csv
reports\calibration\latest\qualification_summary.csv
reports\calibration\latest\top_positive_evidence.csv
reports\calibration\latest\bottom_negative_evidence.csv
reports\calibration\latest\metadata.csv
```

By default, the same command also writes VSA event diagnostic files:

```text
reports\calibration\latest\vsa_event_summary.csv
reports\calibration\latest\vsa_event_stability.csv
reports\calibration\latest\vsa_event_contracts.csv
reports\calibration\latest\vsa_event_metadata.csv
```

Use `--no-reports` to skip all report CSVs. Use `--no-vsa-event-reports` to keep the standard calibration reports but skip the VSA event diagnostics.

## VSA event thresholds

VSA event summaries use `--min-samples` by default. VSA event stability uses `--stability-min-samples` by default.

Override those independently when needed:

```cmd
python audit\run_candidate_audit.py SRF.NS RELIANCE.NS TCS.NS --output reports\calibration\latest --vsa-event-min-samples 10 --vsa-event-stability-min-samples 30
```

## Import-path behavior

When `audit/run_candidate_audit.py` is executed directly, it inserts the repository root at the front of `sys.path` before importing `audit.runner`. This is limited to direct script execution and keeps normal package imports unchanged.

## Boolean parsing

Audit report filters and metadata counts use explicit boolean coercion so CSV-round-tripped strings such as `"False"`, `"0"`, `"no"`, and blank values are not treated as truthy Python strings.
