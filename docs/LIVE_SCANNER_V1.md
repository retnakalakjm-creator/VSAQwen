# Live Scanner v1 — Observation & Decision Pipeline

## Purpose

Live Scanner v1 runs the existing production analysis pipeline against refreshed market data and exposes the resulting evidence, scoring, qualification, and actionability without placing orders.

The scanner is an observation and decision-validation layer. It does not promote provisional evidence, alter scoring policy, or introduce execution logic.

## Pipeline

```text
market data
    ↓
cache / incremental refresh
    ↓
daily → weekly
    ↓
MetricsEngine
    ↓
TrendAnalyzer / market structure
    ↓
EvidenceEngine
    ↓
ScannerEngine
    ↓
observation output
```

The live scanner must reuse the existing production path rather than implement detector or scoring logic independently.

## V1 scope

- CLI execution.
- One or more symbols.
- Periodic refresh using the existing `download_data()` cache/refresh mechanism.
- Latest scanner evaluation through `ScannerEngine.scan_actionable()`.
- Human-readable output.
- Optional JSON output for machine inspection.
- `--once` mode for deterministic validation.
- No broker connection.
- No order generation.
- No automatic trading.

## Evidence policy

The scanner reports evidence according to the current production architecture.

Effort/Result remains contextual-only and zero-weight. Its engine invocation remains disabled.

`DEMAND_COMING_IN`, `INCREASING_DEMAND`, and `SPRING` remain provisional and must not be promoted merely because the live scanner observes them.

## Point-in-time policy

The scanner must not add future information or alternate calculations. Metrics and scanner evaluation must use the same point-in-time semantics already validated by the historical replay path.

V1 does not attempt intrabar prediction. It evaluates the latest available weekly analysis produced from the existing daily data path. Users should treat a still-forming weekly bar as observational rather than as a completed-bar decision.

## Output contract

Each symbol observation includes:

- symbol
- evaluation timestamp
- weekly bar index/date
- qualification
- actionable state
- reason
- net strength
- net pressure
- confidence
- target-bar evidence codes
- scoring evidence codes
- scoring evidence age
- fallback-evidence flag

The JSON representation is intended to become the stable boundary for a future UI or external monitoring process.

## Non-goals

V1 does not:

- change evidence semantics;
- change weights;
- activate Effort/Result;
- activate audit-only events;
- add interaction penalties;
- place orders;
- manage positions;
- infer execution prices;
- replace the historical validation framework.

## Acceptance criteria

1. `--once` produces deterministic output for the same cached dataset.
2. Normal execution refreshes data using the existing cache policy.
3. The scanner uses `MetricsEngine`, `TrendAnalyzer`, `EvidenceEngine`, and `ScannerEngine` rather than duplicate logic.
4. No production scoring configuration is changed.
5. No order/execution dependency is introduced.
6. Output clearly distinguishes actionable decisions from contextual evidence.
