# WF7C2 — Broad-Universe Robustness Study

WF7C2 expands the already read-only WF7C1 research method to larger symbol universes without silently hiding provider/history failures.

## Why this exists

WF7A, WF7B, and WF7C1 did not produce a contradiction rule robust enough for production promotion. The first studies also used a small survivor-biased large-cap universe. A broader cross-sectional study is therefore required before WF7 can be closed.

Large historical universes introduce a separate research risk: one unavailable ticker, insufficient history, provider failure, or scanner-history defect can abort an otherwise useful study. Silently dropping those symbols would be worse because the resulting universe would be unknown and potentially biased.

WF7C2 makes that trade-off explicit.

## Default behavior remains fail-fast

Without an explicit flag, the first symbol-local failure is raised and the study stops. This preserves the previous safety behavior.

```text
requested universe
    ↓
per-symbol full foundation preflight
    ↓
first failure → STOP
```

## Explicit continuation mode

For intentionally large research universes only, the caller may pass:

```text
--continue-on-symbol-error
```

Every symbol-local failure is then recorded with:

- symbol,
- failure stage,
- exception type,
- exception message.

The failure ledger is exported as `wf7c2_symbol_failures.csv`. A study with zero surviving symbols still fails; WF7C2 never emits an empty-universe result.

## Reproducibility contract

Each surviving symbol is run through the full weekly foundation path before aggregate WF7C1 analysis. The exact completed-week OHLCV input is fingerprinted with the existing `weekly-ohlcv-v1` contract.

Those preflight fingerprints become the mandatory expected input for the aggregate WF7C1 rerun. If the data changes between preflight and aggregate analysis, the aggregate run fails instead of mixing data revisions with logic changes.

An optional prior WF7C0/WF7C2 manifest may also be supplied with:

```text
--expected-input-fingerprints <manifest.json>
```

With fail-fast mode, any missing or changed requested symbol stops immediately. With explicit continuation, that symbol is written to the failure ledger at the `fingerprint_gate` stage and excluded transparently.

## WF7C1 methodology is unchanged

WF7C2 does not define a new contradiction rule. After preflight, it calls the existing WF7C1 analysis on the surviving symbol set with the exact preflight fingerprints.

The WF7C1 outputs therefore remain the same research objects:

- episode-start observations,
- opposite-supported treatment episodes,
- regime decomposition,
- symbol-balanced summaries,
- exact matched controls,
- paired close/MFE/MAE differences,
- unmatched treatments.

WF7C2 only adds universe-accounting and reproducibility artifacts.

## Additional artifacts

WF7C2 writes:

- `wf7c2_broad_universe_summary.json`
- `wf7c2_symbol_failures.csv`
- `wf7c2_preflight_input_fingerprints.json`
- `wf7c2_preflight_input_fingerprints.csv`

The standard WF7C1 artifact bundle is written into the same output directory.

## Interpretation gate

A broad-universe study should not be treated as evidence for production promotion unless all of the following are reviewed:

1. requested versus successful symbol counts,
2. every failed/skipped symbol and reason,
3. exact input fingerprints,
4. OOS results,
5. bullish and bearish legacy directions separately,
6. regime-specific samples,
7. symbol-balanced results,
8. matched treatment/control results,
9. sample size and horizon stability.

If the broader study again shows sign reversal, small effective samples, or strong symbol/regime dependence, WF7 should close with no production qualification change.

## Safety boundary

WF7C2 is analysis-only. It changes no detector, evidence weight, score, PatternQualification rule, named-VSA confirmation rule, structural threshold, scanner ranking/actionability, WeeklySetup lifecycle, weekly-to-daily coordination, daily entry, alert, execution, or order behavior.
