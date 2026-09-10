# VSA Qualification Lifecycle API Wiring

PR #82 wires the production-safe qualification lifecycle label helper into the API DTO layer.

## Purpose

The scanner already decides whether a persistent bullish or bearish qualification remains actionable, conflicts with current VSA evidence, lacks confirmation, or has stale/fallback confirmation. The API now exposes that read as a compact label so the local UI and story layer can explain the current state clearly.

## Exposed fields

`QualificationDTO.lifecycle` and `DecisionContextDTO.qualification_lifecycle` can carry this payload:

```json
{
  "qualification": "persistent_bearish",
  "qualification_side": "bearish",
  "status": "invalidated",
  "current_vsa_bias": "bullish",
  "actionable": false,
  "scoring_evidence_age": 0,
  "used_fallback_evidence": false,
  "supporting_event_codes": [],
  "opposing_event_codes": ["demand_coming_in"],
  "ignored_audit_only_codes": [],
  "reason": "Persistent bearish qualification has fresh opposing bullish VSA evidence without same-side support.",
  "production_safe": true
}
```

Status values:

- `active`
- `conflicted`
- `invalidated`
- `expired`
- `needs_follow_through`
- `unqualified`

## Guardrails

This PR is an API/DTO wiring change only.

It does not:

- load market data in the lifecycle helper,
- replay the scanner,
- mutate scanner state,
- change scanner ranking or scoring,
- activate Effort-vs-Result, absorption, or high-volume-reversal production evidence,
- add broker, order, account, funds, holdings, margin, credentials, or position-sizing behavior.

The label is derived from fields already computed by the scanner candidate: qualification, actionability, scoring evidence, scoring-evidence age, and fallback status.

## Cached context behavior

Cached decision-context fast-path responses remain scan-free. When a cached context is returned without a live candidate object, `qualification_lifecycle` may be `null`. Fresh analysis and developing-context responses include the lifecycle payload because the candidate is available in memory.

This avoids a persistence-schema migration and keeps the fast path fast.

## Follow-up

The next small frontend PR can render the lifecycle status in VSA Story / qualification summary. It should continue to avoid scoring/ranking changes and detector activation.
