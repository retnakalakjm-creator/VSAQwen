# VSA Qualification Lifecycle Frontend Display

PR #83 adds a frontend-only display for the production-safe qualification lifecycle labels exposed by PR #82.

## What the VSA Story shows

The VSA Story panel now reads the optional `qualification_lifecycle` field from the decision-context payload and displays:

- Lifecycle status: `active`, `conflicted`, `invalidated`, `expired`, `needs_follow_through`, or `unqualified`.
- Plain-English interpretation of the status.
- Current qualification side and current production-safe VSA bias.
- Supporting and opposing production-safe event codes, rendered as readable labels.
- Any audit-only candidate codes that were deliberately ignored by the backend lifecycle helper.
- Fallback-evidence freshness warnings when the backend marks the lifecycle label as using fallback scoring evidence.

## Confirmed and developing contexts

The display works for both existing VSA Story modes:

- Confirmed weekly context uses completed weekly bars only.
- Developing preview remains clearly labeled as preview context and may change before weekly close.

If a cached confirmed decision context was loaded from the scan-free fast path and does not include an in-memory candidate lifecycle payload, the frontend shows the lifecycle as unavailable instead of inventing a status.

## Scope

This is a frontend-only display PR.

It does not change:

- backend scanner logic
- detector activation
- Effort-vs-Result, absorption, or high-volume-reversal production behavior
- scanner scoring or ranking
- scanner state
- API contracts
- persistence schema
- broker, order, account, funds, holdings, margin, credential, or position-sizing behavior

## Reason

The lifecycle label fixes the user-facing story problem found in LT.NS-style cases: a prior persistent bearish/bullish qualification can now be shown as active, conflicted, invalidated, expired, or needing follow-through instead of appearing as a stale unchanged qualification.
