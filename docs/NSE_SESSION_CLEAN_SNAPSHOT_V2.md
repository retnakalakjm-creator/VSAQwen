# NSE Session-Clean Snapshot v2

## Purpose

Create a new immutable research snapshot that corrects the bounded NSE
session-source defects established by PR #370 without mutating the original
frozen yfinance bundle.

The source of truth remains explicit:

```text
baseline frozen snapshot
    exact manifest SHA:
    45bb7123d2b3b570cf58241f09cb6175f6052d792f92728b194fc587762fb8ff

+ bounded NSE session exception reference

+ official NSE Capital Market bhavcopy files
  for the five genuinely missing live sessions

=
new session-clean v2 snapshot
```

This PR is data-preparation infrastructure only. It does not wire a production
calendar and does not authorize a detector/scanner promotion.

## Why a new snapshot

PR #370 proved two separate source defects across all 30 symbols:

```text
4 exchange-closed dates present as flat zero-volume rows
5 genuine special NSE sessions absent
```

The original frozen bundle remains valuable as a reproducibility baseline.
Therefore v2 is written to a new directory and receives a new deterministic
manifest SHA. The original files are never edited in place.

## Corrective contract

### Remove closed-session placeholders

The builder removes rows only when both are true:

1. the bounded NSE reference marks the date closed; and
2. the frozen row is exactly:

```text
open == high == low == close
volume == 0
```

If a closed-date row has real-shaped OHLCV, the build fails closed instead of
deleting it.

For the frozen 30-symbol bundle, the expected removals are:

```text
2026-05-01
2026-05-28
2026-06-26
2026-09-14

4 rows × 30 symbols = 120 removals
```

### Backfill missing special sessions

The five required live sessions are:

```text
2023-11-12
2024-01-20
2024-03-02
2024-05-18
2026-02-01
```

Because official NSE bhavcopy OHLCV is contemporaneous raw data while the frozen
Yahoo series may be retrospectively restated for later corporate actions, each
backfill also requires the immediately preceding normal NSE session as a
calibration source:

```text
2023-11-10 -> calibrates 2023-11-12
2024-01-19 -> calibrates 2024-01-20
2024-03-01 -> calibrates 2024-03-02
2024-05-17 -> calibrates 2024-05-18
2026-01-30 -> calibrates 2026-02-01
```

For each symbol, the builder derives price and volume scales from the official
calibration row versus the frozen row on the same session. It then applies those
scales to the missing special-session bhavcopy row. This handles later stock
splits/bonuses without hard-coded corporate-action factors.

Use official NSE Capital Market bhavcopy files downloaded from the NSE
**All Reports** page for all ten dates.

The first four dates use the legacy CM bhavcopy era. The 2026 date uses the
UDiFF CM bhavcopy era.

The parser supports both families and normalizes only the EQ series to:

```text
session
nse_symbol
series
open
high
low
close
volume
```

Every missing symbol/session must reconcile to exactly one official `EQ` row.

Expected additions:

```text
5 rows × 30 symbols = 150 additions
```

The previously present 2025-02-01 special Budget session is retained, not
replaced.

## Historical symbol identity

Do not infer that the current Yahoo symbol always matches the historical NSE
symbol.

The known frozen-series exception needed by this backfill is pinned in:

```text
audit/fixtures/nse_session_backfill_symbol_aliases.csv
```

For the 2023/2024 missing sessions:

```text
TMPV.NS -> TATAMOTORS
```

For 2026-02-01 the default current NSE identity is:

```text
TMPV.NS -> TMPV
```

No broad historical rename rule is introduced; only the sessions required by
this repair are mapped.

## Official input provenance

The builder takes explicit local `--bhavcopy` files rather than downloading
inside the audit. Exactly ten sessions are required: five backfills plus their
five calibration sessions.

That is intentional:

- the exact bytes are SHA-256 fingerprinted;
- NSE historical report formats changed across the study window;
- downloaded source files stay inspectable;
- a later run cannot silently receive different remote content.

Accepted source forms:

```text
.csv
.zip containing exactly one recognizable CM bhavcopy CSV
```

If a zip contains multiple recognizable bhavcopy members, the builder fails
rather than guessing.

Reference requirements are documented in:

```text
audit/fixtures/nse_session_backfill_requirements.csv
```

NSE currently documents both the legacy CM bhavcopy reports and the
CM-UDiFF Common Bhavcopy Final report on its All Reports page. The legacy
CM bhavcopy/Common Bhavcopy formats were discontinued from July 8, 2024 in
favor of UDiFF.

## Output

Recommended output directory:

```text
reports/daily-events/input-snapshots/
  milestone6_standard_india_large_cap_30_nse_session_clean_v2/
  2026-09-18/
```

The bundle remains compatible with the existing frozen snapshot loader:

```text
daily_audit_input_manifest.json
daily_audit_input_manifest.csv
snapshots/<SYMBOL>.csv
```

Additional repair provenance:

```text
nse_session_clean_repairs.csv
nse_session_clean_source_files.csv
```

The compatible manifest records:

- original baseline manifest SHA;
- session-exception reference SHA;
- each official bhavcopy source SHA;
- 120 expected removals;
- 150 expected additions;
- net +30 rows across the basket;
- production calendar authorization = false;
- downstream rerun authorization = false.

Each individual symbol must finish with exactly one more daily row than its
baseline source.

## Bar-index consequence

A session-clean dataset has a different row coordinate system.

Therefore old-vs-new identity comparisons must use stable market identity first.

For daily detector emissions:

```text
symbol
session
EvidenceCode
occurrence_on_bar_code
```

For K6:

```text
symbol
session
setup_id / signal_week
direction
```

`bar_index` remains diagnostic metadata but is not a cross-dataset identity
key.

## Safety boundary

This PR does not modify:

- `trading_calendar.py`;
- `daily_completion.py`;
- detectors;
- EvidenceCode;
- scanner transition semantics;
- WeeklySetup authority;
- K6;
- F3;
- M13A;
- scoring;
- qualification;
- actionability;
- alerts/orders.

The resulting v2 bundle is a research input until the downstream semantic diff
is completed.

## Local validation

```powershell
git fetch
git checkout audit/nse-session-clean-snapshot-v2
git pull

python -m ruff check audit/nse_session_clean_snapshot.py scripts/build_nse_session_clean_snapshot.py tests/test_nse_session_clean_snapshot.py

python -m pytest -q tests/test_nse_session_clean_snapshot.py tests/test_nse_session_integrity.py tests/test_daily_input_reproducibility.py

git diff --check origin/main...HEAD
```

## Build

First download the ten official NSE Capital Market bhavcopy files for:

```text
2023-11-10
2023-11-12
2024-01-19
2024-01-20
2024-03-01
2024-03-02
2024-05-17
2024-05-18
2026-01-30
2026-02-01
```

Place them in a local directory, for example:

```text
local-nse-bhavcopy/
```

Then run:

```powershell
python scripts\build_nse_session_clean_snapshot.py `
  --input-snapshot-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30\2026-09-18 `
  --bhavcopy `
    local-nse-bhavcopy\<2023-11-10-file> `
    local-nse-bhavcopy\<2023-11-12-file> `
    local-nse-bhavcopy\<2024-01-19-file> `
    local-nse-bhavcopy\<2024-01-20-file> `
    local-nse-bhavcopy\<2024-03-01-file> `
    local-nse-bhavcopy\<2024-03-02-file> `
    local-nse-bhavcopy\<2024-05-17-file> `
    local-nse-bhavcopy\<2024-05-18-file> `
    local-nse-bhavcopy\<2026-01-30-file> `
    local-nse-bhavcopy\<2026-02-01-file> `
  --output-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30_nse_session_clean_v2\2026-09-18
```

Required output:

```text
symbol_count       = 30
removed_row_count  = 120
added_row_count    = 150
net_row_change     = 30
```

Do not commit the downloaded NSE source archives unless a later project
decision explicitly chooses to vendor them.

## Next gate

After v2 builds successfully:

```text
v1 frozen baseline
        vs
v2 session-clean snapshot
        ↓
session-keyed K5 detector identity diff
weekly candidate / WeeklySetup diff
K6 authority diff
#365 sequence identity diff
#366/#367 outcome diff
F3 timing diff
        ↓
minimum justified rerun set
        ↓
resume M13A
```
