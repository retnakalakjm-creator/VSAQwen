# HIDDEN_DEMAND Research Findings

## Status

**State:** Evidence-validated, production policy still pending.

## Validation ladder completed

- 30-symbol matched-control audit: 495 unique matched pairs.
- 3/5/10-week matched-control deltas: approximately +2.03%, +1.98%, +1.93%.
- Bootstrap robustness: all three horizons remained positive with 95% intervals above zero.
- Context stratification: strongest robust contexts were `healthy + up` and `unknown + range`.
- Symbol concentration: leave-one-symbol-out remained positive and robust for all 30 dropped-symbol cases at all three horizons (90/90 positive rows).
- Policy-value audit: the context-qualified subset outperformed the universal subset at all three horizons, approximately +2.476%, +2.226%, +2.347% versus +2.028%, +1.977%, +1.927%.

## Policy implication

HIDDEN_DEMAND has credible positive incremental value, but the evidence supports context-aware use rather than unconditional bullish weighting.

Candidate promoted contexts:

```text
healthy + up
unknown + range
```

All other contexts remain neutral/excluded until further evidence justifies promotion. Excluded does not mean negative; it means not promoted by the current policy test.

## Weight/actionability finding

The initial actionability sensitivity audit showed that adding a synthetic HIDDEN_DEMAND weight changes production actionability materially because the professional confidence gate moves while strength rises. The baseline had 18 actionable cases out of 106 promoted-context events; each non-zero tested weight changed 34 cases (16 gained, 18 lost).

The changed-decision outcome audit then showed, for every tested weight from 0.10 through 0.30, the same realized outcome profile:

- 3 weeks: gained average about +0.300%; lost average about -4.774%.
- 5 weeks: gained average about +0.424%; lost average about -4.275%.
- 10 weeks: gained average about +5.248%; lost average about -0.565%.

These results are encouraging for decision quality, but the tested weights produced identical changed-case populations. Therefore the current evidence does **not** establish an optimal production weight; it only shows that the actionability boundary is crossed by the synthetic contribution.

## Production decision

**Do not add a HIDDEN_DEMAND production weight yet.**

Before production integration, the next required test is a proper decision-value comparison that treats the changed cases as decision outcomes and establishes whether a chosen weight improves net scanner decisions without creating ranking instability. The existing actionability audit is diagnostic, not sufficient by itself for weight selection.

Production collector, registry, and scoring configuration remain unchanged.
