# Scanner Transition Contract

## Purpose

This document defines the first safe slice of the Phase 4 scanner architecture roadmap: an executable transition contract for the future deterministic scanner engine.

This PR does not replace production scanning. It creates a tested scaffold so later work can migrate production, audit, and replay runners toward one shared transition primitive without changing scanner behavior blindly.

## Contract shape

```python
step(
    state: ScanState,
    bar: MarketBar,
    features: BarFeatures,
) -> tuple[ScanState, BarEvaluation]
```

The first implementation is intentionally conservative. It wraps the current point-in-time scanner behavior and preserves the same semantic output as `ScannerEngine.scan_to_index()`.

## Contract objects

- `MarketBar` carries the stable bar identity: bar index and week.
- `BarFeatures` carries the point-in-time metrics prefix for the current bar.
- `ScanState` carries deterministic scanner history between step calls.
- `BarEvaluation` carries the current trend, evidence, structural-only history entry, and scanner candidate.

## Current behavior

The transition engine currently recomputes the same point-in-time prefix that the existing scanner uses. That is deliberate for the first slice. The goal is correctness equivalence first, not performance.

The transition contract is tested against the existing scanner output for candidate semantics, including:

- qualification
- actionability
- scoring age
- fallback evidence flag
- signal bar identity
- execution bar availability
- ranking score
- net strength and pressure
- scoring evidence
- target-bar evidence
- qualifying evidence
- read-only detector evidence visibility

## Production boundary

The transition contract is not wired into `production_scanner.py` yet.

Production behavior remains unchanged until a later PR explicitly switches one runner at a time behind the full-vs-resume equivalence guardrails.

## Non-goals

- No detector logic changes.
- No scoring/ranking/actionability changes.
- No trade-plan, alert, or order changes.
- No frontend changes.
- No replay/manual-review work.
- No performance optimization in this PR.

## Next safe migration steps

Future PRs should migrate one runner at a time:

1. Make the historical scanner loop use the transition contract internally.
2. Compare every migrated runner against the full-vs-resume equivalence suite.
3. Only after runner equivalence is stable, reduce repeated prefix recomputation.

Do not optimize away prefix recomputation until the shared transition behavior is proven equivalent.
