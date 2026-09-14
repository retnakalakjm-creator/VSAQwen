# Frontend Read-Only Detector Evidence Boundary

## Status

Effort/Result and Absorption are now production-connected backend detector families with frontend read-only visibility.

This frontend display is intentionally limited to evidence review. It does not promote either detector family into scoring, ranking, qualification, actionability, trade-plan generation, alerts, or orders.

## Scope

```text
frontend display                 = YES
backend detector activation       = NO CHANGE
scoring/ranking mutation          = NO
actionability mutation            = NO
trade-plan promotion              = NO
alerts/orders                     = NO
manual-review workflow            = NO
replay/historical replay          = NO
High Volume Reversal              = NOT IN THIS PR
```

## Frontend behavior

The Bar-by-Bar workspace includes a dedicated read-only detector evidence panel for:

- Effort / Result
- Absorption

The panel shows latest matching backend evidence from the production analysis response and labels the families as `Read-only / not scoring`.

When no current matching detector event exists, the panel keeps the detector family visible but marks that no event is present in the current analysis response.

## Selected-week behavior

The selected weekly professional reading now includes a `Read-only Detector Evidence` block directly below the narrative paragraph.

That selected-week block filters the same production analysis response to the selected week and displays any matching read-only detector events for:

- `effort_gt_result`
- `result_gt_effort`
- `absorption`

When the selected week has no matching detector event in the current analysis response, the block states that no Effort/Result or Absorption event is present for that selected week.

The selected-week block is also review-only. It does not change the weekly professional reading text, scanner scoring, ranking, actionability, trade plan, alerts, or orders.

## Roadmap alignment

This follows the roadmap order:

1. Effort/Result backend detector work.
2. Effort/Result production read-only evidence.
3. Absorption production read-only evidence.
4. Frontend read-only visibility for both families.
5. Selected-week frontend read-only evidence visibility.
6. High Volume Reversal backend work next.

Manual-review and historical replay work remain deferred.
