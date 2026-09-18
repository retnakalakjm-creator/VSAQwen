# Historical Revision and Corporate-Action Policy

## Purpose

Routine ProVSA production scans refresh only a recent daily window. That is fast,
but it means an upstream market-data provider can revise an older OHLCV bar
outside the incremental window without the local cache noticing immediately.

Possible causes include:

- exchange/provider corrections,
- backfilled or removed sessions,
- symbol-history maintenance,
- corporate-action processing,
- other upstream restatements.

ProVSA must detect historical change without guessing its cause from chart shape.

## Canonical data policy

Production market-data requests remain:

```text
interval = 1d
auto_adjust = False
period = production configured history window
```

The scanner consumes raw OHLCV. This policy does not introduce adjusted-price
logic and does not infer a stock split, dividend, or other corporate action merely
because prices or volume changed.

## Explicit history revision audit

`audit_cached_history_revision(symbol, provider=...)` is an explicit read-only
operation.

It:

1. loads the current usable local daily cache;
2. downloads a fresh raw/unadjusted production-history window;
3. compares overlapping OHLCV by daily identity;
4. reports changed rows, changed columns, changed/missing dates, and provider-newer
   rows;
5. leaves cache data and metadata unchanged.

Simple append-only new bars are not classified as a historical revision.

A revision is reported when an already-overlapping historical identity changes,
including:

```text
OHLC value changed
volume changed
historical date removed
historical date inserted inside the overlap
```

The audit uses a very small numerical tolerance only to avoid classifying
floating-point representation noise as a provider revision.

## Corporate-action attribution

A historical OHLCV difference is evidence that history changed. It is **not**
sufficient evidence to attribute the change to a split, dividend, bonus issue,
merger, or any other corporate action.

Therefore:

```text
REVISION_DETECTED
!=
CORPORATE_ACTION_CONFIRMED
```

Corporate-action attribution requires an authoritative event source and belongs
in a separate evidence/audit layer if later required.

## Repair policy

This first cut is detection-only.

The audit never:

- rewrites cache data,
- deletes cache data,
- rewrites scanner state,
- changes qualification, scoring, ranking, or actionability,
- forces a full-history rebuild automatically.

If an operator or later explicit repair workflow replaces cached history with a
revised dataset, the existing ScannerState data fingerprint remains the downstream
safety boundary. A checkpoint created from the old historical prefix will fail
fingerprint validation and production scanning will rebuild through the existing
full-replay fallback path when that fallback is allowed.

## Why automatic repair is deferred

A provider disagreement or transient bad response can look like a historical
revision. Automatically replacing years of cached history on first detection
would turn a diagnostic observation into an authoritative market-data mutation.

Promotion to automatic repair therefore requires separate evidence around:

- repeated confirmation,
- provider/source authority,
- rollback,
- audit trail,
- affected-symbol scope,
- operational cost.

Until then, revision detection is diagnostic-only.
