# DEMAND_DRYING_UP Findings

Status: audit-complete; not production-integrated; no production penalty or weight change implemented.

## Detector

`DEMAND_DRYING_UP` is defined as:
- Up/bullish bar
- Low volume
- Narrow spread

The standalone detector exists in `evidence/demand_drying_up.py`.

## Raw point-in-time result

Across the 30-symbol NSE universe:

| Horizon | Cases | Mean Return | Win Rate | Mean MFE | Mean MAE |
| --- | ---: | ---: | ---: | ---: | ---: |
| 3 weeks | 295 | +1.635% | 62.0% | 5.684% | 3.922% |
| 5 weeks | 293 | +2.508% | 60.8% | 7.673% | 4.846% |
| 10 weeks | 289 | +4.047% | 62.3% | 11.972% | 6.868% |

The raw result looked attractive, but raw event returns were not treated as sufficient evidence of incremental value.

## Matched-control result

The matched-control audit used unique controls matched within symbol, direction, state, score/pressure proximity, and VSA-age proximity.

| Horizon | Pairs | Target | Control | Delta |
| --- | ---: | ---: | ---: | ---: |
| 3 weeks | 145 | -0.761% | +0.445% | -1.207% |
| 5 weeks | 143 | -0.883% | +0.692% | -1.575% |
| 10 weeks | 139 | +0.054% | +0.554% | -0.499% |

The attractive raw result disappeared after contextual matching.

## Bootstrap robustness

Using 5,000 bootstrap iterations and 95% percentile intervals:

| Horizon | Pairs | Delta | 95% Low | 95% High |
| --- | ---: | ---: | ---: | ---: |
| 3 weeks | 145 | -1.208% | -2.458% | -0.050% |
| 5 weeks | 143 | -1.576% | -2.997% | -0.181% |
| 10 weeks | 139 | -0.497% | -2.616% | +1.661% |

Conclusion at this stage: robust negative incremental value at 3 and 5 weeks; 10-week effect negative but not statistically robust.

## Context stratification

The completed state × direction × horizon audit used 427 unique matched pairs.

Important patterns:

- `healthy + bearish`: negative at 3w and 5w and still negative at 10w.
- `healthy + bullish`: negative at 3w and 5w; approximately neutral/slightly positive at 10w.
- `unknown`: consistently negative across the audited horizons.
- `correcting`: mostly negative, but bucket sizes are small and intervals remain uncertain.
- `exhausted + bearish`: strongly negative at 10w, but only 5 pairs.
- `exhausted + bullish`: approximately neutral.

No broad context produced a robust positive incremental effect that would overturn the overall negative finding.

## Symbol concentration and robustness

The negative aggregate effect was not explained by a single symbol. Leave-one-symbol-out aggregate deltas remained negative at all audited horizons when individual symbols were excluded.

Per-symbol effects were heterogeneous. Several symbol/horizon buckets were robustly negative, while others were robustly positive. Many detailed buckets were based on small samples.

Therefore no universal symbol-specific penalty was justified.

## Conditional robustness

The predefined targeted negative-context set was compared with its complement.

| Target set horizon | Pairs | Delta | 95% Low | 95% High | Result |
| --- | ---: | ---: | ---: | ---: | --- |
| 3 weeks | 111 | -1.365% | -2.886% | +0.158% | Inconclusive |
| 5 weeks | 110 | -1.978% | -3.768% | -0.255% | Robust negative |
| 10 weeks | 5 | -5.624% | -11.440% | -1.875% | Robust negative; too small for broad promotion |

The complement was inconclusive at all three horizons.

## Production-path reconciliation

A production-path counterfactual audit found:

- 289 standalone DDU detector hits.
- 289 candidate bars evaluated.
- 0 candidate bars retaining DDU in production candidate evidence.
- 0 qualified DDU candidate bars.
- 0 actionable DDU candidate bars.

The cause was architectural, not statistical: `EvidenceEngine.collect()` calls `collect_demand()`, while `collect_demand()` currently does not call `collect_demand_drying_up()`.

Therefore DDU is not currently emitted by the production evidence pipeline.

## Production decision

Do **not** add a production penalty, suppression gate, or professional weight for `DEMAND_DRYING_UP` at this time.

The research establishes that DDU has negative incremental association in the audited research population, particularly at 3–5 weeks, but it does not establish production decision impact because DDU is not presently integrated into the production evidence path.

If DDU is intentionally promoted into production later, the integrated detector must be re-audited through the production path before any weight or actionability change is made.

## Methodological lesson

For every future evidence investigation, keep these questions separate:

1. Does the detector fire?
2. Does production emit and use the evidence?
3. Does changing/removing the evidence alter an actionable production decision?

A result from question 1 or 2 must not be presented as evidence for question 3.
