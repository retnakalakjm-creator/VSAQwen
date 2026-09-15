# VSA Audit Transition Parity

## Purpose

This document records the Phase 4 hardening step after routing the VSA audit default scanner path through `HistoricalScannerRunner`.

The goal is to make the audit migration safer before any production scanner route is changed. The audit path should continue to emit the same compact rows, flags, diagnostics, notes, and bounded replay behavior that it emitted before the default runner was switched to the transition-backed historical runner.

## Guardrail added

The parity tests compare default VSA audit output against an explicitly injected legacy `ScannerEngine` across multiple bounded replay windows.

The comparison covers:

- audit result metadata
- replay row identity
- target event codes
- scoring event codes
- qualifying event codes
- campaign event codes
- structural and VSA event split
- qualification and actionability
- fallback evidence markers
- scoring evidence age
- net pressure and confidence
- audit flags
- detector diagnostics
- notes

## Default runner assertion

The tests also prove that the default audit scanner path instantiates `HistoricalScannerRunner`, while explicit scanner injection remains available for tests and specialized callers.

## Production boundary

This PR does not wire `production_scanner.py` to the transition runner.

It does not change:

- detector logic
- scoring, ranking, qualification, or actionability
- trade-plan, alert, or order behavior
- frontend behavior
- replay/manual-review workflows
- performance behavior

## Next step

After this guardrail passes in CI, the next safe architecture step is a production shadow-comparison test path: compare production scanner output against the transition runner without changing production behavior.
