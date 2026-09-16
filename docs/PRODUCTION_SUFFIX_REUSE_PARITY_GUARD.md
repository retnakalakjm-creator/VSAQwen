# Production Suffix-Reuse Parity Guard

## Purpose

This note defines the safety gate before any Step 6 suffix-reuse optimization is integrated more deeply into the production latest-candidate path.

The migrated historical and audit consumers already use suffix-reuse boundaries, but production optimization stays separate because production also owns checkpoint validation, resume, fallback diagnostics, and snapshot refresh.

## Guarded production cases

`tests/test_production_suffix_reuse_parity_guard.py` freezes the full candidate signature for:

- first-run bootstrap through `scan_latest_candidate_production(...)`;
- valid checkpoint resume through the production resume adapter;
- corrupt-checkpoint fallback through the full replay path and fallback diagnostics;
- actionable wrapper shape through `scan_actionable_production(...)`.

The signature intentionally includes qualification, actionability, ranking/confidence/pressure values, signal and execution identity, fallback evidence state, scoring evidence age, target/scoring/qualifying/campaign evidence codes, Effort/Result evidence, Absorption evidence, high-volume-reversal evidence, and signal-bar anomaly fields.

## Production optimization gate

A later production optimization PR must keep these tests green before changing production suffix-reuse behavior. The expected production result remains exact parity with `ScannerEngine` full point-in-time replay for the latest completed bar.

Any optimization must preserve:

- checkpoint fingerprint validation;
- valid-checkpoint resume behavior;
- corrupt/stale/mismatched checkpoint fallback behavior;
- snapshot refresh behavior;
- fallback diagnostics;
- no-candidate and short-metrics behavior;
- API/frontend output shape through unchanged production DTO inputs.

## Non-goals

This guard does not change scanner runtime logic, detector rules, VSA semantics, scoring, ranking, qualification, actionability, API response shape, frontend runtime, replay/manual-review behavior, HVR policy, trade plans, alerts, or orders.
