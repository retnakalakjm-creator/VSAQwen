# Audit Runner CLI Policy

## Status

Operational documentation for the analysis-only historical candidate audit runner.

The audit runner builds `candidate_outcomes.csv` and optional calibration report CSVs. It does not change production scanner decisions, detector logic, scoring, ranking, qualification, actionability, API output, or live scanner behavior.

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

When reports are enabled, the runner also writes calibration summary files to the same output directory.

## Import-path behavior

When `audit/run_candidate_audit.py` is executed directly, it inserts the repository root at the front of `sys.path` before importing `audit.runner`. This is limited to direct script execution and keeps normal package imports unchanged.
