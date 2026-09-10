# VSA Qualification Lifecycle Frontend Display

PR #83 added a frontend-only display for the production-safe qualification lifecycle labels exposed by PR #82.

PR #84 makes that display lifecycle-aware and easier to read.

## What the VSA Story shows

The VSA Story panel reads the optional `qualification_lifecycle` field from the decision-context payload and displays:

- Lifecycle status: `active`, `conflicted`, `invalidated`, `expired`, `needs_follow_through`, or `unqualified`.
- Plain-English interpretation of the status.
- Current qualification side and current production-safe VSA bias.
- Supporting and opposing production-safe event codes, rendered as readable labels.
- Any audit-only candidate codes that were deliberately ignored by the backend lifecycle helper.
- Fallback-evidence freshness warnings when the backend marks the lifecycle label as using fallback scoring evidence.

## Lifecycle-aware story wording

The headline and summary now respect the lifecycle status.

When the lifecycle status is `expired`, `invalidated`, `conflicted`, or `needs_follow_through`, the frontend does not repeat backend story language that can sound like the old qualification is still validated. Instead, it presents the status as stale, invalidated, conflicted, or waiting for follow-through.

Example:

- Old display risk: `Bearish VSA context in distribution` plus wording that says persistent bearish structure is validated.
- Lifecycle-aware display: `Expired bearish distribution context` plus wording that explains the earlier bearish context is stale and needs fresh confirmation.

This keeps the screen aligned with the lifecycle label without changing scanner logic.

## Readability changes

PR #84 also increases the font size and line height for the detail wording that was difficult to read:

- VSA Story summary text.
- Confirmed/developing mode explanation.
- Qualification lifecycle summary card.
- Lifecycle detail card.
- Confirmation/invalidation detail text.
- Expected-next-behavior text.
- Recent smart-money event detail text.

## Confirmed and developing contexts

The display works for both existing VSA Story modes:

- Confirmed weekly context uses completed weekly bars only.
- Developing preview remains clearly labeled as preview context and may change before weekly close.

If a cached confirmed decision context was loaded from the scan-free fast path and does not include an in-memory candidate lifecycle payload, the frontend shows the lifecycle as unavailable instead of inventing a status.

## Scope

This is a frontend-only display/readability PR.

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

PR #84 makes the surrounding story wording and detail text match that lifecycle status so the screen does not say an old qualification is validated when the lifecycle says it is expired, invalidated, conflicted, or still waiting for follow-through.
