# HIDDEN_DEMAND Research Findings

## Status

**State:** Evidence-validated; **frozen as non-scoring production evidence**.

## Validation ladder completed

- 30-symbol matched-control audit: 495 unique matched pairs.
- 3/5/10-week matched-control deltas: approximately +2.03%, +1.98%, +1.93%.
- Bootstrap robustness: all three horizons remained positive with 95% intervals above zero.
- Context stratification: strongest robust contexts were `healthy + up` and `unknown + range`.
- Symbol concentration: leave-one-symbol-out remained positive and robust for all 30 dropped-symbol cases at all three horizons (90/90 positive rows).
- Policy-value audit: the context-qualified subset outperformed the universal subset at all three horizons, approximately +2.476%, +2.226%, +2.347% versus +2.028%, +1.977%, +1.927%.
- Production-formula sensitivity: non-zero synthetic weights increased strength but reduced confidence, with materially changed actionability.
- Changed-decision outcome audit: every tested weight from 0.10 through 0.30 changed the same 34 cases (16 gained, 18 lost).
- Gain-minus-loss decision-value bootstrap: all tested weights and horizons remained **inconclusive** because the 95% intervals crossed zero.

## Interpretation

HIDDEN_DEMAND has credible positive incremental market value as an empirical observation. The evidence is broad across the 30-symbol universe and survives matched-control, bootstrap, context, and leave-one-symbol-out testing.

However, empirical usefulness does not automatically justify a production score contribution. In the current production scoring architecture, adding HIDDEN_DEMAND changes the demand component and therefore changes strength, weakness, and confidence. The resulting actionability changes are not robustly superior to the baseline when evaluated as gained-versus-lost decision outcomes.

## Frozen production policy

**HIDDEN_DEMAND remains non-scoring.**

It may remain available as evidence/confirmation for research, diagnostics, reports, and future policy review, but it receives **no production demand weight** and must not alter production ranking or actionability.

The context findings (`healthy + up` and `unknown + range`) are retained as research metadata only. They do not constitute permission to add a score contribution.

## Reason for freeze

The final decision-value gate did not establish a statistically robust advantage for any tested production weight:

```text
weight 0.10 → inconclusive at 3/5/10 weeks
weight 0.15 → inconclusive at 3/5/10 weeks
weight 0.20 → inconclusive at 3/5/10 weeks
weight 0.25 → inconclusive at 3/5/10 weeks
weight 0.30 → inconclusive at 3/5/10 weeks
```

Therefore the correct architecture-preserving decision is **no production weight**, rather than selecting a weight by preference or by maximizing raw strength.

## Production impact

Production collector, registry, and scoring configuration remain unchanged.
