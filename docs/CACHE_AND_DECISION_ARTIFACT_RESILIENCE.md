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
