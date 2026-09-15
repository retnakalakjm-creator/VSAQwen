# Scanner Transition Resume Parity

## Purpose

This document records PR #210, the next Phase 4 guardrail after the production full-replay/bootstrap path was routed through `HistoricalScannerRunner`.

The goal is to prove that a durable production `ScannerState` can be translated into the transition-runner state shape and resumed through the transition path while still matching the current `IncrementalScannerEngine.resume_latest` contract.

## Added guardrail

`scanner_transition_resume.py` adds `ScannerTransitionResumeAdapter`, a test/diagnostic adapter that:

- accepts current metrics plus a durable `ScannerState`
- resolves the checkpoint bar by stable `week_beginning` identity
- rejects duplicate or missing checkpoint identities
- seeds transition `ScanState` from persisted structural events
- resumes through `ScannerTransitionEngine.run_to_index(...)`
- returns the latest `ScannerCandidate`

The adapter can also return `TransitionResumeResult` metadata:

- `checkpoint_index`
- `target_index`
- `resumed_bar_count`
- `candidate`

## Covered cases

The tests verify:

- transition resume matches `IncrementalScannerEngine.resume_latest(...)`
- transition resume matches the full scanner contract
- durable `ScannerState` translates into `ScanState` without production wiring
- duplicate checkpoint bar identities are rejected
- missing checkpoint identity is rejected
- `production_scanner.py` is not wired to the new resume adapter yet

## Production boundary

This PR does not switch the valid production checkpoint resume path.

Current production split after this PR remains:

```text
Production full-replay/bootstrap/fallback path -> HistoricalScannerRunner
Valid persisted checkpoint resume path        -> IncrementalScannerEngine
```

`ScannerTransitionResumeAdapter` is a guardrail surface for the next production-wiring slice. It must not change detector behavior, scoring, ranking, qualification, actionability, trade plans, alerts, orders, frontend behavior, or replay behavior.

## Next safe step

After this parity guardrail is green, the next narrow PR can route the valid production checkpoint resume path through this adapter while preserving checkpoint validation, fallback diagnostics, and snapshot refresh behavior.
