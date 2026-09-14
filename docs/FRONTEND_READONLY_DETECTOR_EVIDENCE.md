# Frontend Read-Only Detector Evidence Boundary

## Status

Effort/Result, Absorption, and High Volume Reversal are production-connected backend detector families with frontend read-only visibility.

This frontend display is intentionally limited to evidence review. It does not promote these detector families into scoring, ranking, qualification, actionability, trade-plan generation, alerts, or orders.

## Scope

```text
frontend display                 = YES
backend detector activation       = READ-ONLY DETECTOR FAMILIES ONLY
scoring/ranking mutation          = NO
actionability mutation            = NO
trade-plan promotion              = NO
alerts/orders                     = NO
manual-review workflow            = NO
replay/historical replay          = NO
```

## Frontend behavior

The Bar-by-Bar workspace has one read-only detector evidence display location: directly under the selected week's `Professional Reading` text.

The older separate bottom summary cards were removed so the user does not see two `Read-only Detector Evidence` panels on the same screen.

## Selected-week behavior

The selected weekly professional reading includes a `Read-only Detector Evidence` block directly below the narrative paragraph.

That selected-week block calls the historical audit endpoint for the selected week:

```text
/api/vsa-audit/events?symbols={symbol}&start_week={selected_week}&horizon_weeks=1
```

It displays matching read-only detector event codes from the selected audit row for:

- `effort_gt_result`
- `result_gt_effort`
- `absorption`
- `high_volume_reversal`

When the selected week has no matching detector event in the historical audit response, the block states that no Effort/Result, Absorption, or High Volume Reversal event is present for that selected week.

The selected-week block is review-only. It does not change the weekly professional reading text, scanner scoring, ranking, actionability, trade plan, alerts, or orders.

## Roadmap alignment

This follows the roadmap order:

1. Effort/Result backend detector work.
2. Effort/Result production read-only evidence.
3. Absorption production read-only evidence.
4. Frontend read-only visibility for detector families.
5. Selected-week frontend read-only evidence visibility using historical audit data.
6. High Volume Reversal backend read-only evidence.

Manual-review and historical replay work remain deferred.