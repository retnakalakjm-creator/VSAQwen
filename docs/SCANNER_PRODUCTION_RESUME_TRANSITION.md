# Production Resume Transition Wiring

## Status

PR #211 is the first production valid-checkpoint resume wiring slice for the scanner transition roadmap.

## What changed

Production scanning now uses the transition stack for both production candidate paths:

- Full-replay bootstrap and full-replay fallback continue to use `HistoricalScannerRunner`.
- Valid persisted-checkpoint resume now uses `ScannerTransitionResumeAdapter`.
- State refresh still uses `IncrementalScannerEngine.snapshot(...)` so the durable checkpoint format remains unchanged.

## Why this slice is safe

The previous guardrail PR added `ScannerTransitionResumeAdapter` parity coverage against `IncrementalScannerEngine.resume_latest(...)`. This PR only switches the production valid-checkpoint candidate calculation after that parity layer exists.

The production fallback boundary remains unchanged:

- stale fingerprints still fall back to full replay when fallback is allowed;
- corrupt checkpoints still fall back to full replay when fallback is allowed;
- transition resume failures still emit `ENGINE_DIVERGENCE` diagnostics and fall back to full replay when fallback is allowed;
- `allow_full_replay_fallback=False` still raises instead of silently falling back.

## Non-goals

This PR does not change detector logic, scanner scoring, ranking, qualification, actionability, trade plans, alerts, orders, frontend behavior, or visual replay behavior.

It also does not remove repeated prefix recomputation. That cleanup belongs after transition production wiring is stable.

## Next step

After this PR is merged and CI is green, the next roadmap step is to reduce duplicate runner surfaces and prepare for performance cleanup without changing scanner semantics.
