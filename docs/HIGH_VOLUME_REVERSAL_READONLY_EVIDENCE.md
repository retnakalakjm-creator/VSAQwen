# High Volume Reversal Research Hold

## Status

High Volume Reversal is on hold.

It is not collected as production-visible evidence and should not appear in API, audit, CLI/candidate evidence accessors, or the selected-week Bar-by-Bar read-only detector block.

## Reason

A reversal cannot be reliably defined by a single bar. The previous single-bar trigger profile was too broad and could confuse high-volume stopping/climactic action with a confirmed reversal event.

TradeGuider-style reversal concepts such as Bottom Reversal and 2 Bar Reversal require multi-bar structure and context. ProVSA should not expose a primary High Volume Reversal event until a causal, tested multi-bar rule is designed.

## Boundary while on hold

```text
Production evidence collection    = NO
Historical audit event visibility = NO
Selected-week frontend visibility = NO
Scanner scoring                   = NO
Ranking                           = NO
Qualification                     = NO
Actionability                     = NO
Trade plan                        = NO
Alerts/orders                     = NO
Manual-review workflow            = NO
Replay engine                     = NO
```

## Future requirements before reactivation

Any future HVR implementation should be introduced in a separate PR with:

```text
multi-bar confirmation rules
falling/background context requirements
causal timing, no production lookahead
synthetic regression fixtures
negative tests for ordinary high-volume continuation bars
docs under docs/
read-only evidence first
```

Until then, Effort/Result and Absorption remain the active production-visible read-only detector families.