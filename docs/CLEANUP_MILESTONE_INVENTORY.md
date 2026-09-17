# Cleanup Milestone Inventory

## Purpose

This document starts the cleanup milestone after Step 6 replay reuse closure and the final safety validation on `main`.

The goal is to reduce maintenance drag before starting new daily-entry or confidence-improvement work. Cleanup must preserve the production scanner guarantees that were just closed: same candidates, same VSA evidence semantics, same checkpoint behavior, same API/frontend behavior, and no trade-plan, alert, or order behavior changes.

## Cleanup rule

Do not remove or weaken any guardrail until a focused PR proves it is duplicate, obsolete, or no longer reachable.

Prefer small cleanup PRs with one purpose each:

1. classify and document cleanup targets;
2. consolidate docs;
3. archive or rename non-regression tests;
4. remove only proven-dead compatibility code;
5. delete merged branches only after the local tree and `main` stay stable.

## Protected test groups

Keep these active during cleanup and later feature work:

| Group | Why it is protected |
| --- | --- |
| `tests/test_scanner_transition*.py` | Transition runner contract, replay/resume parity, snapshot behavior, and suffix-reuse boundaries. |
| `tests/test_production*.py` | Production candidate parity, checkpoint behavior, fallback diagnostics, snapshot refresh, replay-reuse measurement, and production closure guardrails. |
| `tests/test_historical_scanner_transition_runner.py` | Ensures production stays behind the historical scanner boundary instead of importing the transition engine directly. |
| `tests/test_scanner_full_resume*.py` | Full replay versus resume parity and durable-state safety. |
| `tests/test_incremental*.py` | Legacy parity oracle and checkpoint-state safety while transition migration remains protected by comparison tests. |
| scanner/ranking neutrality tests | Ensures read-only evidence cannot affect ranking, actionability, alerts, or orders without an explicit future promotion. |
| Effort/Result and Absorption production read-only tests | Protects evidence visibility while keeping those modules out of scoring, ranking, trade plans, alerts, and orders. |

## Cleanup candidates

These are candidates for review, not automatic deletion.

| Area | Candidate cleanup | Safe first action |
| --- | --- | --- |
| Step 6 docs | Several measurement and closure docs now overlap. | Consolidate through `docs/STEP6_REPLAY_REUSE_CLOSURE.md` and link older docs instead of expanding each one. |
| Archived visual replay tests | Already moved outside default pytest collection. | Keep archived unless replay/manual-review work becomes active again. |
| Shadow/manual-review evidence docs | Some may be superseded by later production read-only evidence docs. | Inventory before deletion; preserve anything that documents non-scoring boundaries. |
| Compatibility fallbacks for older test doubles | Added to keep staged PRs safe while boundaries changed. | Review only after all production and transition tests remain green on `main`. |
| Low-priority manual tools | `tools/historical_validation.py` remains outside production Step 6 closure. | Leave unchanged unless a dedicated tooling cleanup PR is opened. |
| Merged milestone branches | Many milestone branches are now merged. | Delete remote branches only after cleanup plan and final safety stay stable. |

## Suggested cleanup PR sequence

### Cleanup PR 1: inventory and guardrails

Current document. No runtime or test behavior change.

### Cleanup PR 2: documentation consolidation

Make `docs/STEP6_REPLAY_REUSE_CLOSURE.md` the single Step 6 landing page. Older docs should either:

- stay as historical detail and link back to the closure page; or
- be shortened if they repeat the same final inventory.

No scanner code or tests should change in this PR.

### Cleanup PR 3: test-suite inventory cleanup

Use the current collected test inventory to classify tests as:

- core regression;
- production safety guard;
- transition migration guard;
- audit/research support;
- frontend/API contract;
- archived/manual-reference only;
- duplicate candidate.

Do not delete broad groups yet. Mark only obvious non-regression/manual artifacts.

### Cleanup PR 4: compatibility fallback review

Review compatibility branches added around:

- production full-replay candidate plus snapshot reuse;
- production resume snapshot reuse;
- snapshot adapter test doubles;
- resume adapter test doubles.

Remove a fallback only if all current tests prove it is unreachable or unnecessary.

### Cleanup PR 5: merged branch cleanup

Delete merged remote branches after code/docs cleanup is stable. Keep any branch that still has an open PR, unmerged work, or useful recovery context.

## Validation guidance

Docs-only cleanup PRs need human review only.

Test/docs cleanup PRs should run the focused tests touched by the cleanup.

Runtime or compatibility cleanup PRs should run:

```powershell
python -m pytest tests/test_production_replay_reuse_measurement_guard.py -v
python -m pytest tests/test_production_resume_snapshot_reuse.py -v
python -m pytest tests/test_production_bootstrap_snapshot_reuse.py -v
python -m pytest tests/test_production_suffix_reuse_parity_guard.py -v
python -m pytest -v (Get-ChildItem tests -Filter "test_scanner_transition*.py").FullName
python -m pytest -v (Get-ChildItem tests -Filter "test_production*.py").FullName
python -m pytest

cd frontend
npm run build
```

## Non-goals

This cleanup milestone does not introduce daily-entry logic, SMC scoring, new VSA rules, actionability changes, trade plans, alerts, or orders.

Those belong after cleanup, starting with a weekly VSA setup to daily-entry trigger bridge in shadow/read-only mode.
