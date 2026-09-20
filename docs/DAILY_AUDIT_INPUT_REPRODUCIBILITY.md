# Daily Audit Input Reproducibility

## Purpose

Daily research audits must not depend on whichever mutable production cache
happens to exist on a machine.

Production data loading remains unchanged and continues to use its configured
rolling history. This audit layer instead downloads an explicit full-history
dataset, truncates it to a fixed session cutoff, writes normalized read-only
snapshots, and fingerprints the exact OHLCV inputs.

## Snapshot contract

Each symbol snapshot contains only:

- session
- open
- high
- low
- close
- volume

The manifest records:

- audit id and fingerprint version
- basket name
- provider
- requested period
- fixed cutoff
- symbol
- row count
- first and last session
- SHA-256
- snapshot path

The fingerprint uses normalized sessions plus exact IEEE-754 numeric values.
Loading a snapshot recomputes the fingerprint and fails if the file was changed.

## Safety

This layer is research-only and non-actionable.

It does not change:

- production download period
- production cache contents
- scanner behavior
- evidence detectors
- scoring or ranking
- alerts or orders

The builder bypasses `download_data()` and therefore does not read or mutate
the production cache.

## Build the standard 30-symbol snapshot

```powershell
python scripts/build_daily_audit_inputs.py --cutoff 2026-09-18
```

The default output is:

```text
reports/daily-events/input-snapshots/<basket>/2026-09-18/
```

A pre-existing manifest is not overwritten silently. Use `--overwrite` only
when intentionally replacing an audit snapshot.

## Validation

```powershell
python -m ruff check audit/daily_input_reproducibility.py scripts/build_daily_audit_inputs.py tests/test_daily_input_reproducibility.py
python -m pytest -q tests/test_daily_input_reproducibility.py
```

After this layer is validated, the next change should make L1 consume these
verified snapshots. L2 and L3 can then derive from the same frozen input lineage.
