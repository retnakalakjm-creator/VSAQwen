# Cache and Decision Artifact Resilience

## Purpose

ProVSA must keep symbol analysis available when local persisted files are stale, incompatible, or unreadable.

This document covers two runtime safety cases:

1. A symbol has a `.parquet` cache file, but the local Python environment cannot load a usable Parquet engine.
2. A persisted decision-context or decision-journal file is invalid, legacy, or corrupt.

## Parquet cache fallback

Parquet remains a preferred cache format when the local environment supports it. Some Windows environments can have Parquet libraries installed but blocked by application-control policy, DLL loading rules, or incompatible wheels.

When a symbol has only an unusable `.parquet` cache and no `.csv` fallback, ProVSA should now treat the Parquet file as a cache miss. The normal data path then downloads fresh daily OHLCV data and writes the CSV fallback format.

Expected behavior:

- Existing usable Parquet cache: read Parquet.
- Existing CSV fallback with unusable Parquet engine: read CSV.
- Existing unusable Parquet-only cache: download fresh data and write CSV.
- No cache: download fresh data and write the best available local cache format.

This prevents one symbol cache from causing `/analysis`, `/decision-context`, or `/api/vsa-audit/events` to return a 500 solely because Parquet cannot be read on the current machine.

## Decision artifacts

Decision context and journal files are local decision-support artifacts. They must not be treated as authoritative market data, and they must not make the scanner fail when they are invalid.

Decision-context reads already treat invalid files as cache misses before rebuilding analysis.

Decision-journal upsert now follows the same resilience rule during `/analysis` persistence: if the existing journal file cannot be read or uses an unsupported schema, ProVSA treats it as empty and overwrites it with the current valid entry.

This keeps `/analysis` available for the symbol while preserving the scanner's current market read.

## Scope guardrails

This change is operational resilience only.

It does not change:

- VSA detector logic.
- High Volume Reversal, Absorption, or Effort/Result event criteria.
- Scoring, ranking, qualification, actionability, trade plans, alerts, or orders.
- Frontend behavior except that fewer symbol requests should fail due to bad local files.

## Local recovery note

Before this fix is merged locally, the workaround for Parquet-engine failures is to delete the affected `.parquet` cache files from the repo `cache/` folder so CSV can be rebuilt.

After this fix is active, that manual symbol-by-symbol cleanup should no longer be required for Parquet-only cache files.


## Cache data/metadata generation consistency

The daily cache file and its metadata sidecar are separate files, so replacing them
cannot be one filesystem-atomic operation. ProVSA therefore treats the metadata as
diagnostic rather than authoritative and adds two protections:

1. cache data + metadata writes for one symbol are serialized with a cross-process
   file lock;
2. new metadata records a `generation_id` derived from the SHA-256 digest of the
   exact finalized cache file.

`inspect_cache_generation(symbol)` can report:

```text
generation_match
generation_mismatch
legacy_metadata_without_generation
metadata_missing
metadata_invalid
metadata_format_unsupported
data_missing
```

This detects interrupted commits and unexpected out-of-band cache-file changes.
It does **not** reject otherwise usable OHLCV data. Cache generation consistency
is operational telemetry and repair evidence, not a VSA/scanner decision input.

Existing version-1 metadata remains readable. It is reported as
`legacy_metadata_without_generation` until the cache is next rewritten.


## Historical revision auditing

Incremental cache refresh cannot discover every provider correction outside its
recent merge window. ProVSA therefore provides an explicit read-only historical
revision audit. See `docs/HISTORY_REVISION_POLICY.md`.

The audit is diagnostic-only: it does not rewrite cache history and does not
infer a corporate action from OHLCV changes.
