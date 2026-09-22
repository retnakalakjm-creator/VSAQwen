# Daily Behavior Evidence-Collision Universe Audit

## Purpose

PR #364 established that the existing DailyBehavior sequence study can preserve
two identities at once:

```text
coarse DailyBehaviorDimension sequence
+
exact supporting EvidenceCode sequence
```

The first genuine LT.NS rerun showed that 48 of 65 fresh sequence observations
belonged to coarse signatures containing multiple distinct evidence narratives.

That result justified a broader frozen-universe audit before any behavior
remapping is considered.

This audit answers:

```text
Across the frozen 30-symbol India large-cap basket,
how often do coarse DailyBehavior sequences hide multiple
distinct exact VSA evidence narratives?
```

It remains research-only and non-actionable.

## Frozen source

The runner consumes the existing deterministic daily snapshot:

```text
reports/daily-events/input-snapshots/
  milestone6_standard_india_large_cap_30/
  2026-09-18/
```

The source manifest is loaded and fingerprint-verified through the existing
daily audit input contract.

No market-data download occurs.

## Per-symbol preparation

Each symbol is prepared independently:

```text
frozen daily OHLCV
        |
        +--> production weekly scanner/materializer
        |       -> historical WeeklySetup authority
        |
        +--> cached causal K5 daily Evidence
        |
        +--> K6 causal WeeklySetup -> daily direction assignments
        |
        v
DailyBehaviorSequenceStudyInput
```

The cached K5 producer is already parity-tested against the explicit legacy
prefix replay with exact observation/evidence equality.

## Parallelism

Symbols are independent, so preparation may use a process pool.

Default CLI worker count:

```text
4
```

The sequence study itself runs only after all requested symbols prepare
successfully.

No failed symbol is silently dropped.

## Fail-closed policy

The runner records:

```text
daily_behavior_collision_failures.csv
```

If any requested symbol fails preparation:

- the standard multi-symbol sequence study is not run;
- the universe summary records the failures;
- the CLI exits non-zero.

This prevents accidental survivor-only research.

## Standard study artifacts

When all symbols succeed, the existing K3 bundle writer emits:

```text
daily_sequence_study_summary.json
daily_sequence_input_fingerprints.json
daily_sequence_input_fingerprints.csv
daily_sequence_symbol_failures.csv
daily_sequence_records.csv
daily_sequence_outcomes.csv
daily_sequence_signature_summaries.csv
daily_sequence_signature_collisions.csv
```

The existing coarse `signature` remains the outcome grouping key.

The exact `evidence_signature` remains audit provenance only.

## Universe metadata

The wrapper additionally emits:

```text
daily_behavior_collision_universe_summary.json
daily_behavior_collision_symbol_summary.csv
daily_behavior_collision_failures.csv
```

The universe summary records:

- frozen snapshot basket;
- cutoff;
- manifest SHA-256;
- worker count;
- requested/succeeded/failed symbols;
- total daily bars and evidence;
- weekly candidate/setup counts;
- bullish/bearish direction-assignment counts;
- sequence/outcome counts;
- coarse collision counts;
- collision observation counts.

## Safety boundary

This audit does not change:

- any detector;
- any EvidenceCode mapping;
- any DailyBehaviorDimension mapping;
- weekly qualification;
- WeeklySetup authority;
- scanner scoring;
- ranking;
- confidence;
- actionability;
- DailyEntry;
- alerts or orders.

It only measures information loss inside the current coarse behavior abstraction.

## Recommended validation path

First run focused code tests:

```powershell
python -m ruff check audit/daily_behavior_collision_universe.py scripts/audit_daily_behavior_collision_universe.py tests/test_daily_behavior_collision_universe.py

python -m pytest -q tests/test_daily_behavior_collision_universe.py tests/test_daily_behavior_sequence_outcomes.py tests/test_daily_behavior_sequence_runner.py tests/test_offline_daily_evidence.py

git diff --check origin/main...HEAD
```

Then run a three-symbol smoke study:

```powershell
python scripts\audit_daily_behavior_collision_universe.py `
  --input-snapshot-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30\2026-09-18 `
  --output-dir reports\daily-behavior-sequences\collision-universe\smoke-3 `
  --workers 3 `
  --symbols LT.NS SRF.NS ADANIPORTS.NS
```

If the smoke run succeeds with zero failures, run the full basket:

```powershell
python scripts\audit_daily_behavior_collision_universe.py `
  --input-snapshot-dir reports\daily-events\input-snapshots\milestone6_standard_india_large_cap_30\2026-09-18 `
  --output-dir reports\daily-behavior-sequences\collision-universe\milestone6_standard_india_large_cap_30_frozen_2026-09-18 `
  --workers 4
```

## Interpretation rule

A high collision rate does not itself justify remapping behavior dimensions.

The next decision requires examining:

- which exact evidence narratives collide;
- bullish versus bearish symmetry;
- symbol breadth;
- event-frequency concentration;
- whether forward outcomes differ materially between evidence variants;
- whether any distinction remains robust after controlling for context.

Only then should a later PR consider mechanism-level behavior semantics.
