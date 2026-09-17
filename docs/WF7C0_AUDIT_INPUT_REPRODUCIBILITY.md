# WF7C0 — Historical Audit Input Reproducibility Contract

## Purpose

WF7A and WF7B historical reruns differed by one legacy-actionable observation. That does not invalidate either audit, but it demonstrates that live historical data can change between study runs.

WF7C0 separates **data drift** from **logic drift** before later weekly-production decisions are considered.

The contract is analysis-only.

## Captured identity

For every symbol, WF7C0 fingerprints the exact completed weekly frame passed into `MetricsEngine` during the same historical-study invocation.

The fingerprint records:

```text
symbol
fingerprint version
row count
first completed week
last completed week
canonical OHLCV columns
SHA-256
```

Canonical columns:

```text
week_beginning
open
high
low
close
volume
```

The hash preserves row order. Numeric values are encoded with Python's exact IEEE-754 `float.hex()` representation so CSV formatting, locale, and display rounding do not affect identity.

Derived metrics are deliberately excluded. WF7C0 identifies the market input entering `MetricsEngine`, not the output of later engines.

## Same-run capture

The reproducibility runner does not download history a second time to compute the hash.

Instead:

```text
daily_loader(symbol)
        ↓
completed_weekly_only(daily_to_weekly(daily))
        ↓
FINGERPRINT THIS EXACT FRAME
        ↓
MetricsEngine
        ↓
existing weekly foundation audit
```

This avoids a false reproducibility check in which the audit and hash are built from separate downloads.

## Comparison semantics

`compare_weekly_audit_inputs()` compares two fingerprint sets and reports:

```text
symbols missing from either run
version changes
row-count changes
first/last-week changes
hash changes
canonical-column contract changes
```

A matching hash means the canonical completed-week OHLCV values and row order are identical under the same fingerprint version.

A mismatch is evidence that the market-data input changed. It is **not** by itself evidence that scanner logic changed.

## Artifacts

The CLI exports:

```text
weekly_input_fingerprints.json
weekly_input_fingerprints.csv
```

Example:

```powershell
python -m audit.weekly_input_reproducibility_runner --symbols "RELIANCE.NS,HDFCBANK.NS" --horizons "5,10,15" --out-of-sample-start-week "2024-01-01" --output-dir "reports/weekly-foundation/wf7c0-study-01"
```

## Interpretation gate

Before comparing two future promotion/contradiction studies:

```text
fingerprints identical
    → logic/result comparison is valid on identical market history

fingerprints different
    → first identify the changed symbol/history
    → do not attribute output differences solely to code
```

## Safety boundary

WF7C0 changes none of the following:

```text
detectors
evidence weights
PatternQualification
structural thresholds
named-VSA confirmation
scanner score/rank/actionability
WeeklySetup
weekly-to-daily coordination
daily entry
execution
alerts
orders
```

`is_actionable` remains false.

## Next step

After reproducibility is validated, WF7C1 can study `OPPOSITE_SUPPORTED_THESIS` using frozen/verified input identity, direction/regime stratification, and symbol-balanced or matched controls.
