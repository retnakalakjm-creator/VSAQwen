# Effort/Result and Absorption Calibration

## Purpose

This document records the production-read-only detector calibration made after the JUBLFOOD.NS May 2026 audit case exposed a useful backend quality gap.

The audit showed rows where the scanner already emitted diagnostics such as:

- `review_potential_effort_gt_result`
- `review_potential_absorption`

Those diagnostics meant the audit layer could see likely Effort/Result or Absorption behavior, but the production evidence collectors were still too strict to emit the corresponding read-only evidence codes.

## Production boundary

The calibrated detector output remains read-only.

Allowed:

- Emit `EFFORT_GT_RESULT` when very high volume produces limited result through narrow/normal spread or muted downside.
- Emit `ABSORPTION` when high-volume bearish bars make a lower low but recover to the midpoint or better.
- Surface those codes through existing production evidence, API, CLI, and frontend read-only views.
- Keep tests around the read-only boundary.

Not allowed in this calibration step:

- Scoring changes.
- Ranking changes.
- Qualification changes.
- Actionability changes.
- Trade-plan promotion.
- Alerts or orders.
- Manual-review workflow.
- Replay UI or historical replay engine work.
- Symbol-specific hardcoding.

## Detector intent

### Effort > Result

The calibrated Effort/Result rule recognizes very-high-volume effort when the result is comparatively muted. Muted result may appear as narrow, below-average, or average spread, or as limited downside progress compared with the previous close.

### Absorption

The calibrated Absorption rule recognizes a high-volume bearish bar that makes a lower low but closes around the midpoint or better. This keeps the concept focused on supply being absorbed rather than on ordinary weakness.

## Roadmap position

This calibration follows the production read-only integrations for Effort/Result and Absorption and the frontend read-only evidence visibility work.

High Volume Reversal remains a later backend detector-family item after this calibration PR.
