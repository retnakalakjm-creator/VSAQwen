# Full Scanner Incremental Equivalence

**Validation date:** 2026-09-01  
**Status:** PASS / milestone closed

## Purpose

Verify that the scanner resumed from persisted causal state produces the same production outcome as rebuilding the scanner from full history.

The validation covers the full production decision path, not only swing detection:

```text
Swing state
    -> Trend / structural state
    -> VSA evidence
    -> Qualification
    -> Professional scoring
    -> Actionability / final decision
```

## Validation ladder

| Validation | Result |
|---|---:|
| Swing checkpoint equivalence | 90/90 PASS |
| Full production-path equivalence | 6/6 PASS |
| Full scanner incremental equivalence — 2 symbols | 6/6 PASS |
| Full scanner incremental equivalence — 8 symbols | 24/24 PASS |
| Full scanner incremental equivalence — 30 symbols | **90/90 PASS** |

The final 30-symbol audit used three historical checkpoints per symbol: 60%, 70%, and 80% of the available metrics history.

## Final result

```text
symbols: 30
split ratios: 60%, 70%, 80%
checkpoints: 90
passed: 90/90
status: PASS
```

Every tested checkpoint reported equivalent production outcomes. Across the final audit, `ScoreDelta` was `0.000000` for every reported case.

Both actionable and non-actionable outcomes were covered. Actionable cases matched on actionability and score; non-actionable cases matched on the production non-actionable outcome.

## Failure discovered and resolved

The 30-symbol audit initially produced:

```text
89/90 PASS
```

The only failure was:

```text
COALINDIA.NS @ 80%
target = 661
FullAct = True
IncAct  = False
ScoreDelta = 0.000000
```

Targeted diagnostics showed that scoring, VSA evidence, campaign evidence, pressure, strength, confidence, and fallback state were already identical. The difference was qualification caused by missing post-checkpoint structural progression events.

The checkpoint state itself was then verified to contain the same 18 structural progression events as the full historical run. The specific qualifying events in the full run occurred at bars 805, 811, and 816.

Root cause: the continuation state truncated confirmed swings to `STRUCTURE_LOOKBACK` before resuming structural processing. That retained-window assumption was not sufficient to reproduce the causal structural campaign required by professional progression qualification.

The correction was to preserve the complete confirmed swing history in the scanner continuation state. After the correction:

```text
COALINDIA.NS
60%  PASS
70%  PASS
80%  PASS
```

and the complete 30-symbol audit subsequently passed 90/90.

## Architectural conclusion

The incremental scanner continuation path is validated against the current production scanner for the tested 30-symbol / three-checkpoint matrix.

Derived outputs such as professional scores, qualification, and final decisions are not treated as authoritative persisted state. Causal state is resumed and the production evaluation path is reused.

This milestone should be considered closed unless later scanner changes modify the causal state model, swing logic, structural filtering, evidence history, qualification, scoring, or final decision contract. Any such change should rerun the equivalence audit before being treated as regression-safe.

## Reproduction

Final audit command:

```bash
python tests/run_full_scanner_incremental_equivalence_audit.py --all-symbols
```

Expected final summary:

```text
=== EQUIVALENCE SUMMARY ===
passed: 90/90
status: PASS
```
