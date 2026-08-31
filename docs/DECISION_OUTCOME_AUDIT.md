# Decision Outcome Audit

## Status

**Type:** Audit infrastructure

**State:** PROPOSED / audit-only

This layer connects the production scanner decision to future market outcomes without changing production scoring or qualification.

## Counterfactual design

For a point-in-time candidate bar:

```text
production EvidenceResult
        ↓
      baseline scanner decision

same EvidenceResult
        ↓
remove confirmation-only evidence
        ↓
 masked scanner decision
```

Both decisions use the same trend, historical qualification state, target bar, and scoring window. Only confirmation-only evidence is removed.

The outcome label is computed independently from future bars only.

## Outcome fields

The audit records:

- signal bar index;
- directional side;
- horizon completeness;
- signed forward return;
- maximum favorable excursion;
- maximum adverse excursion;
- baseline actionability and score;
- masked actionability and score.

MFE and MAE are non-negative magnitudes. Forward return is directional: positive means favorable movement for the tested side.

## Important limitation

This harness measures decision impact and attaches future outcomes, but it does not define a production success threshold. Threshold selection, risk-adjusted objectives, and trade-management assumptions must be validated separately before any scoring change.

## Validation requirements

Before using historical results, verify:

- the replay target and signal index refer to the same production bar;
- the future window begins strictly after the signal bar;
- incomplete horizons are excluded from outcome statistics;
- baseline and masked decisions use identical structural/history inputs;
- no production scorer or qualification rule is modified by the audit;
- each audit run has deterministic replay and a known sample count.
