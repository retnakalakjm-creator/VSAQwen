# LT Visual Replay Manual Review Template

This is the final manual-review template before recording real LT visual replay outcomes.

Use this file only after opening the dev-only visual replay and visually inspecting the offline LT cases. Do not mark a case as `pass` or `fail` from code output alone.

## Scope and safety boundary

- Purpose: human manual review of visual replay evidence.
- Data source: offline replay fixtures only.
- Production behavior change: none.
- Scanner state change: none.
- Scoring, ranking, actionability, detector, API, frontend, persistence, alert, or order behavior change: none.
- A separate production PR is still required after shadow validation.

## How to review

1. Open the dev-only visual replay route.
2. Load the offline fixture for the LT case.
3. Step through the replay bar around the event week.
4. Compare visible markers with the expected marker labels.
5. Inspect pre-event VSA/SMC context.
6. Inspect post-event follow-through or counterfactual behavior.
7. Save or reference a screenshot/evidence artifact.
8. Record reviewer, timestamp, notes, lane outcomes, and final outcome.
9. Keep a case `undecided` if any required lane is not visually confirmed.

Allowed lane values: `pass`, `fail`, `undecided`.

Allowed final case values: `pass`, `fail`, `undecided`.

Do not use `pass` unless every required lane is `pass` and the visual replay evidence supports the expected behavior.

Use `fail` when at least one required lane fails or the visual replay contradicts the expected behavior.

Use `undecided` when evidence is incomplete, ambiguous, missing, or not yet reviewed.

## Required review lanes

- `marker_alignment_recheck`
- `pre_event_context_recheck`
- `post_event_follow_through_recheck`
- `counterfactual_quality_check`
- `vsa_smc_quality_judgment`
- `evidence_artifact_traceability`

---

## Case 1: LT.NS | 2025-02-24 | STRUCTURAL_WEAKENING

- Case ID: `LT.NS|2025-02-24|STRUCTURAL_WEAKENING`
- Symbol: `LT.NS`
- Event week beginning: `2025-02-24`
- Target: `STRUCTURAL_WEAKENING`
- Offline fixture: `offline_replay/LT_2025-02-24.json`
- Expected marker labels:
  - `effort_without_result`
  - `supply_present`
  - `structural_weakening`
  - `follow_through_required`

### Reviewer evidence

- Reviewer:
- Reviewed at:
- Evidence artifact / screenshot reference:
- Replay route / environment:
- Notes:

### Lane outcomes

| Lane | Outcome | Evidence notes |
| --- | --- | --- |
| `marker_alignment_recheck` | `undecided` |  |
| `pre_event_context_recheck` | `undecided` |  |
| `post_event_follow_through_recheck` | `undecided` |  |
| `counterfactual_quality_check` | `undecided` |  |
| `vsa_smc_quality_judgment` | `undecided` |  |
| `evidence_artifact_traceability` | `undecided` |  |

### Final case outcome

- Final outcome: `undecided`
- Reason:
- Blocking issues, if any:

---

## Case 2: LT.NS | 2026-03-02 | RESULT_GT_EFFORT

- Case ID: `LT.NS|2026-03-02|RESULT_GT_EFFORT`
- Symbol: `LT.NS`
- Event week beginning: `2026-03-02`
- Target: `RESULT_GT_EFFORT`
- Offline fixture: `offline_replay/LT_2026-03-02.json`
- Expected marker labels:
  - `result_greater_than_effort`
  - `demand_absorption`
  - `constructive_follow_through`
  - `counterfactual_required`

### Reviewer evidence

- Reviewer:
- Reviewed at:
- Evidence artifact / screenshot reference:
- Replay route / environment:
- Notes:

### Lane outcomes

| Lane | Outcome | Evidence notes |
| --- | --- | --- |
| `marker_alignment_recheck` | `undecided` |  |
| `pre_event_context_recheck` | `undecided` |  |
| `post_event_follow_through_recheck` | `undecided` |  |
| `counterfactual_quality_check` | `undecided` |  |
| `vsa_smc_quality_judgment` | `undecided` |  |
| `evidence_artifact_traceability` | `undecided` |  |

### Final case outcome

- Final outcome: `undecided`
- Reason:
- Blocking issues, if any:

---

## Next step after filling this template

After both LT cases have real visual evidence, convert the completed review into the existing manual review result fixtures/reports:

- `audit/fixtures/effort_result_visual_replay_shadow_review_results_pending.json`
- `audit/fixtures/effort_result_visual_replay_lt_manual_evidence_review_packet_pending.json`
- downstream completion, handoff, summary, and integration-gate reports

Only after the downstream shadow gates pass should a separate production PR be considered.
