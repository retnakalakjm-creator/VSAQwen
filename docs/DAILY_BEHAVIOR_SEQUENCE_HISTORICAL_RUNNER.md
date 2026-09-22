# Daily Behavior Sequence Historical Runner

## Purpose

K3 runs the already-defined K1 sequence audit and K2 outcome study across an
explicit multi-symbol research universe.

The runner does **not** create daily evidence from price bars and does **not**
reconstruct weekly setup direction. Those inputs must already be prepared
point-in-time by the caller.

## Prepared symbol input

Each symbol input contains:

```text
symbol
completed daily price bars
point-in-time visible weekly direction by daily bar
point-in-time daily Evidence
```

Only daily bars with an explicit weekly-direction assignment are replayed. This
makes the causal setup visibility decision an input to the study rather than a
hidden heuristic in the runner.

## Study path

```text
prepared symbol input
        ↓
input validation + fingerprint
        ↓
K1 DailyBehaviorSequence per assigned daily bar
        ↓
K2 fresh-sequence forward outcomes
        ↓
multi-symbol exact-signature descriptive summaries
```

The runner does not infer missing weekly directions, backfill setup visibility,
or create evidence from OHLCV.

## Input reproducibility

The fingerprint covers exactly the fields consumed by K3:

- normalized symbol;
- daily bar index values;
- close/high/low price history used by K2;
- weekly direction assignments;
- evidence records used by K1.

Equivalent logical ordering of weekly-direction assignments and evidence produces
the same fingerprint.

An optional expected fingerprint manifest can gate a rerun. A mismatch is a hard
failure by default.

## Universe failure policy

Default behavior is fail-fast.

Large research studies may explicitly set `continue_on_symbol_error=True`.
When enabled, every skipped symbol is written to the failure ledger with:

```text
symbol
stage
error_type
message
```

A study cannot silently shrink its universe without leaving that record.

## Research artifacts

The bundle writer emits:

- summary JSON;
- input fingerprint JSON and CSV;
- symbol failure ledger CSV;
- per-bar sequence record CSV;
- causal outcome observation CSV;
- exact coarse-signature descriptive summary CSV;
- coarse-signature/evidence-signature collision CSV.

Sequence and outcome rows retain the existing coarse `signature` and now also
expose an `evidence_signature` containing the exact supporting EvidenceCode
lineage. The collision artifact identifies coarse behavior cohorts that contain
multiple distinct evidence narratives. Existing outcome grouping remains based
on the coarse signature.

Every exported research row remains non-actionable.

## Safety boundary

K3 is analysis-only.

It does not:

- run a new daily evidence detector;
- change WeeklySetup visibility;
- change DailyBehavior mappings;
- change F3 fresh-signal semantics;
- rank sequence signatures;
- set sequence thresholds;
- alter qualification/ranking/actionability;
- create alerts or orders.

K3 makes sequence/outcome research reproducible. It does not interpret the study
result as evidence for promotion.

See `docs/DAILY_BEHAVIOR_EVIDENCE_IDENTITY.md` for the audit-only distinction
between coarse behavior identity and exact supporting-code identity.
