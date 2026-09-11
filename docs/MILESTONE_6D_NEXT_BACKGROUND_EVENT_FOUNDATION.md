# Milestone 6D: Next Background-Event Foundation

Milestone 6D starts after the Milestone 6C recovery-sequence foundation and saved-output validation chain.

The goal of this phase is not visual replay, scanner activation, or profit/loss backtesting. The goal is to define the next conservative background-event foundation so the project can keep improving event semantics before anything is promoted into production scoring or chart replay.

Project doctrine:

```text
foundation first, visualization second
```

## Position in the roadmap

Milestone 6A established the audit foundation and showed that broad detector activation was still too noisy.

Milestone 6B added lifecycle supersession review behavior:

```text
persistent_bearish + fresh demand/reversal evidence
  -> conflicted
  -> pending_supersession = true
```

and then exposed the narrow review state:

```text
status = supersession_review
```

Milestone 6C defined and validated the conservative recovery sequence:

```text
prior weakness
  -> stopping volume / supply absorption clue
  -> spring or shakeout test
  -> fresh demand follow-through
  -> review-only recovery-sequence candidate
```

Milestone 6D should now focus on the next background-event foundation instead of moving directly to the deferred visual replay milestone.

## Recommended 6D focus

The recommended next focus is an audit-only Absorption background foundation.

Working name:

```text
absorption_background_review
```

This should remain explicitly review-only. It should not imply automatic accumulation, trade readiness, bullish reversal, scanner promotion, or score/rank improvement.

## Why Absorption is next

Absorption appears in several parts of the current audit vocabulary and is already adjacent to recovery-sequence work.

Existing terminology includes:

```text
supply_absorption
review_potential_absorption
stopping_volume
increasing_supply
supply_coming_in
hidden_supply
structural_progression_weakening
demand_coming_in
increasing_demand
persistent_bearish
conflicted
pending_supersession
supersession_review
```

6C used `supply_absorption` as a possible recovery anchor, but it did not define a broader absorption background. That is the gap 6D should close.

The main question is not whether an isolated absorption clue is bullish. The question is whether absorption-style evidence changes the background context enough to deserve review while supply blockers, stale evidence, fallback evidence, and lifecycle conflict remain visible.

## Primary 6D question

6D should answer one question:

```text
When does absorption-style evidence represent a meaningful background change instead of ordinary noisy volume or unresolved supply?
```

This is a background-context question, not a single-bar detector question.

## Candidate background shape

A conservative absorption-background review shape is:

```text
prior weakness or supply pressure
  -> absorption-style evidence appears
  -> selling pressure fails to extend or is met by demand
  -> fresh demand/reversal evidence follows
  -> same-window blockers are checked
  -> review-only absorption-background candidate
```

The output should be a review marker only.

## Required components

### 1. Prior supply or weak background

Absorption should not be treated as meaningful without context. Useful prior context may include:

```text
persistent_bearish
increasing_supply
supply_coming_in
hidden_supply
structural_progression_weakening
buying_climax
markdown / distribution-style context
```

Without prior supply pressure, an absorption clue can be overfit.

### 2. Absorption-style evidence

Initial 6D evidence should start from existing codes and diagnostics only, such as:

```text
supply_absorption
review_potential_absorption
stopping_volume
```

Important distinction:

```text
supply_absorption = production event code when present
review_potential_absorption = diagnostic/audit hint only
```

Diagnostic hints must stay separate from production evidence.

### 3. Failure of supply to extend

Absorption should require evidence that supply pressure did not simply continue dominating.

The first version can model this conservatively using saved-row windows and blocker checks, not new market-data calculations.

### 4. Fresh demand or reversal follow-through

Clean review candidates should require fresh non-fallback evidence such as:

```text
demand_coming_in
increasing_demand
high_volume_reversal
```

Stale or fallback evidence should downgrade the result.

### 5. Blocker review

Same-window supply or structural weakness should block or downgrade a clean absorption-background review, especially:

```text
increasing_supply
supply_coming_in
hidden_supply
structural_progression_weakening
```

A blocked case may still be useful in a casebook, but it should not become a clean background-change candidate.

## Production-safe baseline

The strongest safe default remains lifecycle review, not automatic bullish promotion.

If absorption-style evidence appears against active bearish context, the conservative lifecycle interpretation remains:

```text
conflicted + pending_supersession
```

or, if chart-confirmed and unblocked:

```text
supersession_review
```

6D must not bypass the 6B lifecycle foundation.

## Allowed 6D work

Allowed implementation should be narrow:

```text
audit-only or review-only absorption-background marker
saved-output normalizer/casebook support if needed
unit tests for context, follow-through, blockers, stale/fallback evidence
label-firing audit for saved outputs
casebook report for manual review
```

The implementation can identify a case that deserves review. It must not make the setup automatically tradable.

## Disallowed 6D work

6D must not introduce:

```text
broad detector activation
automatic bullish flip
profit/loss strategy backtest
scanner ranking or scoring weight changes
TradingView-style replay UI
frontend chart annotation
provider or market-data loading changes
persistence changes unless explicitly scoped
```

## Interaction with 6C recovery sequence

6C and 6D should remain separate.

6C asks whether a specific recovery sequence exists:

```text
Stopping Volume -> Spring / Shakeout -> Demand follow-through
```

6D asks whether absorption-style evidence changes the background context enough to deserve review.

Absorption may support a future recovery sequence, but it should not automatically substitute for Spring/Shakeout behavior. Likewise, a 6C recovery marker should not automatically become an absorption-background marker unless the absorption evidence is explicit.

## Review checklist before coding

Before writing a 6D code PR, confirm the intended behavior against this checklist:

1. Prior weakness or supply pressure exists before the absorption review.
2. Production absorption evidence is distinguished from diagnostic-only hints.
3. Diagnostic-only absorption does not promote a clean label by itself.
4. Fresh demand or reversal follow-through is required for a clean review candidate.
5. Stale or fallback evidence does not qualify a clean background change.
6. Same-window supply or structural weakness can block or downgrade the result.
7. Persistent bearish lifecycle state remains conservative.
8. 6C recovery-sequence logic is not silently reused as a substitute for absorption background.
9. Scanner ranking, scoring, provider calls, replay behavior, persistence, API, and frontend behavior remain unchanged unless explicitly scoped.
10. The implementation can be validated with small unit tests before expanded-basket reruns.

## Test expectations for a future code PR

A future 6D implementation PR should include focused tests for:

- valid prior supply pressure -> absorption evidence -> fresh demand follow-through;
- absorption hint without production evidence producing no clean review label;
- production absorption without prior weakness producing no clean background review;
- demand follow-through without absorption context producing no clean absorption review;
- stale evidence producing no clean review;
- fallback evidence producing no clean review;
- same-window supply blocker downgrading or blocking the result;
- persistent bearish context remaining conflicted/pending-supersession instead of flipping bullish;
- chart-confirmed and unblocked case being eligible only for review/supersession-review behavior;
- audit-only candidate codes remaining outside production scoring and ranking.

## Validation plan

After implementation, the correct next step is label-firing validation and casebook review, not visual replay or P/L backtesting.

Use saved-output audit validation to answer:

```text
Did absorption-background review fire only where prior supply context exists?
Did diagnostic absorption hints remain diagnostic-only?
Did fresh demand/reversal evidence matter?
Did stale/fallback evidence stay blocked?
Did unresolved supply prevent clean background-change labeling?
Did lifecycle interaction remain conservative?
Did the expanded basket expose false positives or misses?
```

Use the expanded basket as the repeatable validation baseline:

```text
milestone6_expanded_india_large_mid_60
```

Use the same anchor set for continuity unless the 6D audit identifies stronger absorption-specific cases:

```text
LT.NS
DRREDDY.NS
GRASIM.NS
AMBUJACEM.NS
GODREJCP.NS
BRITANNIA.NS
TMPV.NS
```

## Visual replay holding area

Visual replay remains valuable, but it should not become the next active implementation phase yet.

Correct order:

```text
6D background-event plan
6D review-only marker
6D casebook/export if needed
6D label-firing audit validation
casebook review
visual replay later, after event semantics are stable
```

A replay UI is only trustworthy when the labels it displays are trustworthy.

## Current 6D status

6D starts as a planning milestone.

The next safe implementation step is a narrow review-only absorption-background marker with direct unit tests.

No detector family should be broadly activated before the background gates, blocker behavior, stale/fallback behavior, and lifecycle interaction are proven.
