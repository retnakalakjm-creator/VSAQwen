# Scanner Fallback Diagnostics

## Purpose

Production scanning may fall back to a full point-in-time replay when a persisted scanner checkpoint cannot be trusted. The fallback keeps the app available, but it must not silently hide checkpoint defects.

This document records the diagnostic policy for PR #202.

## Policy

Normal first-run bootstrap remains quiet. A symbol with no saved scanner state is expected to run a full replay and then save a fresh checkpoint.

A diagnostic is recorded only when ProVSA rejects or cannot resume an existing checkpoint.

Diagnostics are operational only. They do not change scanner evidence, scoring, ranking, qualification, actionability, trade plans, alerts, or orders.

## Diagnostic codes

| Code | Meaning |
| --- | --- |
| `CHECKPOINT_CONFIG_MISMATCH` | Saved scanner state was created under a different scanner/trend/evidence configuration. |
| `CHECKPOINT_DATA_MISMATCH` | Historical OHLCV data before or at the saved checkpoint no longer matches the saved data-prefix fingerprint. |
| `CHECKPOINT_STALE` | More than one compatibility fingerprint is stale, or the mismatch is not limited to only config or only data. |
| `CHECKPOINT_CORRUPT` | Saved scanner state cannot be loaded or validated as a usable state file. |
| `ENGINE_DIVERGENCE` | Saved state loaded and passed fingerprints, but incremental resume could not process current metrics. |

`CHECKPOINT_MISSING` is intentionally defined but not emitted for normal bootstrap, because missing state on first run is not a defect.

## Expected behavior

When fallback is allowed:

1. Record the diagnostic.
2. Run full replay for the latest bar.
3. Save a fresh checkpoint at the latest completed bar.
4. Return the same candidate semantics protected by the full-vs-resume equivalence contract.

When fallback is disabled, ProVSA should raise the original state/resume error instead of converting it into a diagnostic fallback.

## Non-goals

- No detector logic changes.
- No new evidence events.
- No scoring/ranking/actionability changes.
- No frontend feature work.
- No replay/manual-review work.
- No symbol-specific handling.
