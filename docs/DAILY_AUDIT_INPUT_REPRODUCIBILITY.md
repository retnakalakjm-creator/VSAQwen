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

## Run L1 from the frozen bundle

The daily-event inventory runner can consume a verified snapshot bundle directly:

```powershell
python scripts/audit_daily_event_inventory.py --now 2026-09-18T16:00:00+05:30 --input-snapshot-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30\2026-09-18
```

Snapshot mode:

- verifies the manifest and each symbol fingerprint before replay
- never calls the production `download_data()` path
- rejects `--refresh`
- replays independent symbols in spawned worker processes
- defaults to at most 4 workers while leaving one logical CPU free
- accepts `--workers N` for an explicit worker count
- schedules longer histories first to reduce end-of-run stragglers
- prints per-symbol completion progress to stderr
- restores basket order before building the final L1 ledger
- terminates the worker pool on Ctrl+C
- records the snapshot audit id, manifest SHA-256, basket, period, and cutoff in the L1 summary
- writes to a separate `*_frozen_<cutoff>` L1 directory by default

Parallelism changes only wall-clock execution. Each worker runs the same existing
causal K5 prefix replay for one symbol, and the final aggregate is rebuilt in
the original requested symbol order.

For an explicit four-worker full-basket run:

```powershell
python scripts/audit_daily_event_inventory.py --now 2026-09-18T16:00:00+05:30 --input-snapshot-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30\2026-09-18 --workers 4
```

This makes the L1 ledger traceable to one exact frozen market-data lineage.

