# DEMAND_DRYING_UP Research Record

## Status

**Research complete for the current production architecture. No production scoring, weight, or suppression change is justified.**

## Detector and production-path finding

`DEMAND_DRYING_UP` has a standalone detector in `evidence/demand_drying_up.py` using the audited definition of an up/bullish bar with low volume and narrow spread.

The current `EvidenceEngine.collect()` path calls `collect_demand()`, but `collect_demand()` does not call `collect_demand_drying_up()`. Therefore the standalone DDU detector is not currently wired into production evidence emission.

This distinction is critical: an event can have measurable historical outcome attribution while having zero current production decision exposure.

## Research performed

The DDU investigation progressed through:

1. Raw/point-in-time event audit.
2. Matched-control outcome analysis.
3. Bootstrap robustness analysis.
4. State × direction × horizon stratification.
5. Symbol concentration analysis.
6. Per-symbol bootstrap robustness and leave-one-symbol-out analysis.
7. Conditional context robustness analysis.
8. Production-path counterfactual attempt and reconciliation.

The universe used for the later audits was 30 requested symbols, with 30 scanned and 427 unique matched pairs in the matched-control research.

## Context-stratified result

The completed context audit showed the following broad pattern:

- Healthy bearish: negative at 3w and 5w, also negative at 10w.
- Healthy bullish: negative at 3w and 5w; approximately neutral/slightly positive at 10w.
- Unknown: consistently negative across the audited horizons.
- Correcting: mostly negative, but uncertain because of small samples.
- Exhausted bearish: strongly negative at 10w, but based on only 5 cases.
- Exhausted bullish: approximately neutral.

No broad context showed a strong, well-supported positive incremental effect that would reverse the overall DDU conclusion.

## Symbol concentration result

The negative aggregate effect was not explained by one or two symbols. Leave-one-symbol-out aggregate deltas remained negative at the audited horizons when individual symbols were removed.

At the same time, per-symbol results were heterogeneous: several symbol/horizon buckets were robustly negative, while others were robustly positive. Many symbol/context buckets had very small sample sizes.

Therefore a universal symbol-specific penalty would not be methodologically justified.

## Conditional robustness result

The predefined targeted negative-context set was compared with the complement.

At 5 weeks, the targeted set showed a robust negative incremental effect:

- 110 pairs
- mean delta: -1.978%
- 95% bootstrap interval: -3.768% to -0.255%

At 3 weeks, the targeted set was negative but inconclusive:

- 111 pairs
- mean delta: -1.365%
- 95% interval: -2.886% to +0.158%

At 10 weeks, the targeted set was robustly negative but contained only 5 pairs:

- mean delta: -5.624%
- 95% interval: -11.440% to -1.875%

The complement was inconclusive at all three horizons.

Context-level bootstrap intervals remained mostly inconclusive because the individual context buckets were much smaller. The only clearly robust individual context was exhausted/bearish at 10 weeks, again with only 5 pairs.

## Production counterfactual / reconciliation

An audit run found:

- 289 standalone DDU detector hits.
- 0 candidate bars retaining DDU through the production candidate evidence.
- 0 qualified DDU candidate bars.
- 0 actionable DDU candidate bars.
- 0 target-context actionable DDU bars.

The immediate cause was then traced to the architecture: the standalone DDU detector is not invoked by the production `EvidenceEngine.collect()` → `collect_demand()` chain.

Consequently, a production DDU suppression gate would currently have no candidates to suppress. The counterfactual therefore cannot establish production decision impact until DDU is intentionally integrated into the production evidence path.

## Final research conclusion

`DEMAND_DRYING_UP` currently has **negative empirical association in the audited research population**, especially in the targeted 5-week context set. The effect is not driven by a single symbol.

However:

- effects are heterogeneous by symbol and horizon;
- several detailed context buckets remain statistically inconclusive;
- the strongest 10-week targeted result has only 5 cases; and
- most importantly, DDU is not currently emitted by the production EvidenceEngine.

### Production decision

**Do not add a production penalty, suppression gate, or weight change for DEMAND_DRYING_UP at this time.**

### Architecture decision

Keep DDU as an audit/research detector unless and until there is an explicit decision to promote it into the production evidence path. If promoted later, repeat the production-path actionability and counterfactual validation using the integrated detector rather than reusing the current standalone-event result as if it were production evidence.

## Methodological lesson

For future evidence audits, distinguish these three questions:

1. Does the detector fire?
2. Does production actually emit and use the evidence?
3. Does changing/removing the evidence alter an actionable scanner decision?

A negative answer to the second question makes a production counterfactual for the evidence meaningless until integration exists.

## Audit engineering rule

Before committing any future audit/debug script, verify:

- loop structure and replay complexity;
- data-loading count;
- production-path consistency;
- imports and symbol availability;
- object/API compatibility;
- point-in-time causality;
- expected sample sizes;
- and avoidable repeated computation.

The audit runner should use one chronological replay per symbol whenever the production path requires replay history, rather than rebuilding the full prefix once per detected event.
