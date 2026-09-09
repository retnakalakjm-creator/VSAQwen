# Milestone 5 Plan: Live Integration Validation and Release Hardening

## Purpose

Milestone 5 turns the Milestone 4 implementation into a reliable local live workflow.

Before adding new product features, the first goal is to run the current backend and frontend together, verify that the confirmed/developing/context/journal/provider status work behaves as expected, and document any bugs found during live use.

This milestone remains decision-support only. It must not add order placement, order modification, order cancellation, position sizing, account access, holdings, funds, margins, broker mutation APIs, or credential persistence.

## Why live integration comes first

The previous milestones added several connected pieces:

```text
confirmed weekly decision context
developing preview context
frontend confirmed/developing toggle
decision journal display and evaluation
data-source diagnostics endpoint
frontend provider/cache freshness panel
read-only Upstox provider scaffold
read-only Upstox readiness helper
developing-context persistence guard
```

Unit tests verify isolated behavior, but the local app still needs an end-to-end validation pass to confirm:

```text
backend route wiring
frontend request ordering
symbol changes and stale-response guards
cache metadata display
stale-cache warning behavior
confirmed vs developing labels
journal refresh behavior
provider diagnostics visibility
Windows local run steps
```

Milestone 5 therefore starts with a live integration gate.

## Phase 0: Milestone 4 live integration gate

### Goal

Run the current `main` backend and frontend locally and verify that all Milestone 4 features work together without changing scanner semantics.

### Required checks

1. Start the FastAPI backend.
2. Start the Next.js frontend.
3. Analyze a normal yfinance symbol such as `SRF.NS`.
4. Confirm the compact confirmed VSA Story loads before or with full analysis.
5. Confirm the full chart analysis loads and remains synchronized with the confirmed story.
6. Click `Developing preview` and confirm it is visibly labeled as developing.
7. Switch back to `Confirmed weekly` and confirm the confirmed story remains the default source of truth.
8. Confirm the decision journal panel loads without requiring `persist_status=true`.
9. Confirm the data-source panel shows provider/cache details.
10. Confirm no broker/order/account wording or behavior appears in the UI.
11. Run the Upstox readiness helper without printing token values.
12. If Upstox is configured locally, run the optional read-only fetch check.
13. Record any UI/API/runtime mismatch before adding new feature work.

### Local commands

```bash
python -m uvicorn api.main:app --reload
```

```bash
cd frontend
npm run dev
```

```bash
python tools/check_upstox_provider_config.py --symbol RELIANCE.NS
```

Optional read-only Upstox fetch check:

```bash
python tools/check_upstox_provider_config.py --symbol RELIANCE.NS --fetch
```

### Acceptance criteria

Milestone 5 feature work should not begin until:

```text
confirmed context loads correctly
developing preview is clearly labeled and opt-in only
confirmed/developing views do not overwrite each other
journal panel loads and remains read-only by default
data-source panel shows useful provider/cache status
stale-cache warning is understandable when present
Upstox readiness helper hides token values
no broker/order/account scope is introduced
any live integration bugs are converted into focused PRs
```

## Phase 1: Release smoke-test checklist

### Goal

Add a repeatable local release checklist so every future milestone can be validated consistently.

### Todo

- Add `docs/local_smoke_test.md` or `docs/release_checklist.md`.
- Include backend startup steps.
- Include frontend startup steps.
- Include yfinance default-provider validation.
- Include optional Upstox readiness validation.
- Include confirmed/developing story checks.
- Include journal checks.
- Include data-source diagnostics checks.
- Include stale-cache fallback checks.
- Include a final forbidden-scope checklist.

### Acceptance criteria

- A contributor can follow the checklist on Windows 11 or a standard local Python/Node setup.
- The checklist clearly separates required yfinance checks from optional Upstox checks.
- The checklist does not require broker order/account permissions.

## Phase 2: CI safety net

### Goal

Add GitHub Actions so backend tests and frontend builds run automatically on pull requests.

### Todo

- Add a backend test job running `pytest`.
- Add a frontend build job running `npm ci` and `npm run build`.
- Keep jobs lightweight and deterministic.
- Avoid requiring live Upstox credentials in CI.
- Avoid network-dependent provider tests except normal package installation.

### Acceptance criteria

- Pull requests show Python test status.
- Pull requests show frontend build status.
- CI does not require broker credentials.
- CI does not run order/account/broker mutation code.

## Phase 3: Frontend error and empty-state polish

### Goal

Make local live failures easy to understand without confusing them with scanner decisions.

### Todo

- Improve backend-offline message.
- Improve not-enough-bars message.
- Improve no-cache-metadata-yet state.
- Improve stale-cache warning copy.
- Improve Upstox selected-but-disabled warning.
- Improve Upstox token-missing warning.
- Improve Upstox symbol-not-mapped warning.
- Improve developing-preview unavailable state.
- Keep confirmed story visible when secondary panels fail.

### Acceptance criteria

- The user can tell the difference between scanner output, data-source diagnostics, and app/runtime errors.
- Failure states do not imply trade recommendations.
- Confirmed context remains the default decision-support view.

## Phase 4: Local deployment documentation

### Goal

Document the exact local workflow for running ProVSA as a local professional terminal.

### Todo

- Add Windows-oriented setup notes.
- Document Python virtual environment setup.
- Document backend dependency installation.
- Document frontend dependency installation.
- Document environment variables.
- Document yfinance default behavior.
- Document optional Upstox read-only setup.
- Document cache directory behavior.
- Document state directory behavior.
- Document how to reset local cache/state safely.

### Acceptance criteria

- A fresh local checkout can be brought up without reading old chat history.
- Upstox setup is explicitly optional.
- Credentials are kept outside the repository.

## Phase 5: Optional read-only watchlist status

### Goal

Add a lightweight status view for multiple symbols without running a full scanner pass for every symbol.

### Todo

- Accept a small watchlist of symbols.
- Show provider/cache/stale status for each symbol.
- Show whether a confirmed context exists.
- Avoid triggering expensive full analysis unless explicitly requested.
- Keep the endpoint read-only.

### Acceptance criteria

- Users can quickly identify missing/stale data across a watchlist.
- No broker/account/order scope is added.
- Batch status does not silently run heavy scanner loops.

## Phase 6: Optional release notes

### Goal

Summarize what changed across Milestones 1-5 in a human-readable release note.

### Todo

- Summarize completed weekly-bar safety work.
- Summarize scanner performance work.
- Summarize decision context work.
- Summarize journal work.
- Summarize provider/data-source work.
- Summarize frontend live workflow work.
- Document remaining known limitations.

### Acceptance criteria

- The project has a clear local-terminal release summary.
- Remaining work is easy to prioritize.

## Future Milestone: Dedicated trade-planning layer

After the UI refactor, add a separate analysis-only trade-planning layer. This layer can translate a confirmed VSA context into trader-facing planning language such as posture, pullback/breakout preference, invalidation area, and reward/risk expectation. It must remain decision-support only and must not place, modify, cancel, size, or route orders.

## Future Milestone: Swing Scanner dashboard

Add a scanner dashboard that identifies swing-trading candidates from the existing confirmed weekly decision-support pipeline.

### Candidate criteria

- Bullish background.
- Fresh demand signals.
- Limited supply.
- Favorable trend.
- Acceptable risk.

### Intended dashboard summary

```text
====================================================================================
                    PROFESSIONAL VSA SWING SCANNER
====================================================================================

Analysis Date : <current analysis date>

Stocks Scanned          : <count>
Bullish Candidates      : <count>
Watchlist               : <count>
Bearish Candidates      : <count>

Market Background       : <plain-English market background>
Average Swing Score     : <plain-English or score-derived summary>

Top Sector
-----------------------
Banking
Capital Goods
IT
Pharma
```

### Boundary

The Swing Scanner must use confirmed completed weekly bars for official candidates. It must not add broker orders, account access, holdings, funds, margins, or credential persistence.
