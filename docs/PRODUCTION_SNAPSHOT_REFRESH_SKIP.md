# Production Snapshot Refresh Skip

## Purpose

This guardrail keeps the Phase 4 transition-runner migration from doing avoidable checkpoint work on unchanged data.

After production resume moved to `ScannerTransitionResumeAdapter`, production still refreshes durable scanner state with `IncrementalScannerEngine.snapshot(...)`. That refresh is required when the stored checkpoint is missing, stale, corrupt, behind the latest bar, or replaced after a resume failure.

It is redundant when a loaded checkpoint has already passed fingerprint validation and its `last_closed_bar` is the latest metrics bar.

## Contract

Production may skip `IncrementalScannerEngine.snapshot(...)` only when all of these are true:

1. A persisted scanner state was loaded successfully.
2. Engine/config/data fingerprints passed validation.
3. The persisted state's `last_closed_bar` matches the latest metrics `week_beginning`.
4. Transition resume completed without falling back to full replay.

Production must still refresh the snapshot when:

- no checkpoint exists;
- the checkpoint is stale, corrupt, or fingerprint-mismatched;
- the checkpoint is valid but behind the latest bar;
- transition resume fails and production falls back to full replay.

## Boundaries

This is a performance/internal cleanup only.

It does not change:

- detector rules;
- Effort/Result or Absorption evidence;
- scoring, ranking, qualification, or actionability;
- API or frontend contracts;
- replay/manual-review behavior.

## Validation

`tests/test_production_resume_transition_wiring.py` covers both sides of the contract:

- old valid checkpoint still resumes through `ScannerTransitionResumeAdapter` and refreshes to the latest bar;
- already-latest valid checkpoint still resumes through `ScannerTransitionResumeAdapter` but skips the redundant snapshot rebuild.
