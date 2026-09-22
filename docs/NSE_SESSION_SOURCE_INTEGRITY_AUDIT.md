# NSE Session Source-Integrity Audit

## Purpose

This audit measures whether the frozen daily OHLCV research source agrees with
known NSE cash-market session exceptions before ProVSA changes any production
calendar behavior.

It separates two failure classes that must not be conflated:

1. **calendar inference defects**
   - a weekday-only calendar treats an NSE holiday as a trading session;
   - a weekend-only rule misses a specifically announced Saturday/Sunday session.

2. **market-data source defects**
   - a frozen provider snapshot contains a row for an exchange-closed date;
   - a frozen provider snapshot omits an exchange-open special session.

A production calendar fix alone cannot reconstruct OHLCV for a missing real
session. Therefore the data-source audit comes first.

## Scope

Reference coverage is intentionally bounded:

```text
2021-09-01 through 2026-09-18
```

The fixture records only dates that differ from the ordinary Monday-Friday rule:

```text
weekday holiday / exceptional closure
    -> expected_session = closed

announced Saturday/Sunday live session
    -> expected_session = open
```

Ordinary weekdays and ordinary weekends are not duplicated in the fixture.

The frozen 30-symbol snapshot contains history older than this reference window.
The audit therefore reports:

```text
reference_window_covers_full_snapshot_history = false
```

and explicitly forbids using the bounded fixture as a production calendar.

## Initial confirmed examples

The frozen source contains flat zero-volume rows on dates that the NSE 2026
capital-market holiday circular marks closed, including:

```text
2026-05-01
2026-05-28
2026-06-26
2026-09-14
```

The frozen LT.NS source also omits the announced Sunday live trading session on:

```text
2026-02-01
```

These examples establish that the problem is not limited to
`TradingCalendar.next_session()`: the source OHLCV itself can disagree with
exchange session identity.

## Authoritative reference classes

The committed exception ledger is derived from NSE exchange circulars for:

- annual Capital Market trading holidays;
- revisions to announced holiday dates;
- exceptional exchange closures;
- special live Saturday/Sunday trading sessions;
- weekend Muhurat/Budget sessions when the Capital Market segment is open.

Examples include:

- NSE/CMTR/71775 — 2026 Capital Market trading holidays;
- NSE/CMTR/72349 — February 1, 2026 live trading session;
- NSE/CMTR/57285 — 2023 Bakri Id holiday revision;
- NSE/MSD/60300 — January 20, 2024 special live session;
- NSE/MSD/61893 — May 18, 2024 special live session;
- NSE/CMTR/59124 — November 12, 2023 Sunday Muhurat session.

The fixture is evidence for this bounded audit only. Full-history production
authority requires a separately reviewed session source across the entire period
used by production/replay.

## Outputs

```text
nse_session_integrity_summary.json
nse_session_integrity_symbols.csv
nse_session_integrity_anomalies.csv
```

Anomalies are classified as:

```text
UNEXPECTED_CLOSED_SESSION_ROW
MISSING_SPECIAL_SESSION_ROW
UNREFERENCED_WEEKEND_ROW
```

For rows that occur on an exchange-closed date the audit also records whether:

```text
open == high == low == close
volume == 0
```

so synthetic carry-forward/provider placeholder rows are visible rather than
silently treated as real bars.

## Safety boundary

This PR must not modify:

- `trading_calendar.py`;
- `daily_completion.py`;
- detector semantics;
- frozen detector identities;
- weekly scanner authority;
- K6 behavior;
- F3 timing;
- M13A timing;
- scoring/ranking/qualification/actionability;
- alerts/orders.

No downstream study is authorized to rerun from this PR alone.

## Decision gate

After the bounded audit:

```text
if no source anomalies:
    continue to full-history calendar construction

if phantom closed-date rows exist:
    define audited source-cleaning policy
    before detector/K5/K6 reruns

if missing special-session rows exist:
    source replacement or authoritative backfill is required
    because a calendar cannot synthesize OHLCV

then:
    extend session authority across full frozen history
    -> exact K5/K6/F3 diff audit
    -> determine minimum downstream rerun set
    -> resume M13A only after timing/source parity is established
```

## Validation

```powershell
python -m ruff check audit/nse_session_integrity.py scripts/audit_nse_session_integrity.py tests/test_nse_session_integrity.py

python -m pytest -q tests/test_nse_session_integrity.py tests/test_trading_calendar.py tests/test_completed_daily_only.py tests/test_weekly_daily_coordinator.py tests/test_daily_trigger_replay.py

git diff --check origin/main...HEAD
```

Run against the frozen snapshot:

```powershell
python scripts\audit_nse_session_integrity.py `
  --input-snapshot-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30\2026-09-18 `
  --output-dir reports\nse-session-integrity\bounded-2021-09-01_2026-09-18
```
