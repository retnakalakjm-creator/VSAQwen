# Local Live Integration Smoke Test

## Purpose

This checklist verifies the Milestone 4 work in a real local run before new Milestone 5 feature work.

Run it against real market data through the local backend/frontend. The goal is to confirm that the live app wiring works as expected without changing scanner semantics.

This checklist is decision-support only. It must not require order placement, order modification, order cancellation, position sizing, account access, holdings, funds, margins, broker mutation APIs, or credential persistence.

## Key implementation check before live testing

The confirmed FastAPI analysis path should use the production scanner wrapper:

```text
ProVSAService.analyze_symbol()
-> _completed_weekly_for_symbol()
-> _analyze_symbol_from_weekly()
-> scan_latest_candidate_production(...)
```

The confirmed API route must not call `ScannerEngine().scan_to_index(...)` directly for every analysis request.

Expected behavior:

- First confirmed analysis for a symbol/timeframe may bootstrap scanner state through a full point-in-time scan.
- Later confirmed analysis requests should resume through the incremental production scanner when valid scanner state exists.
- If scanner state is missing, invalid, or incompatible, the guarded full-replay fallback may rebuild state.
- Developing preview is separate and may use `ScannerEngine().scan_to_index(...)` because it is preview-only, does not save scanner state, does not persist decision context, and does not create journal entries.

If the confirmed API path is found to call `ScannerEngine().scan_to_index(...)` directly, stop and create a focused implementation PR before continuing feature work.

## Required local setup

From the repository root:

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

For the frontend:

```bash
cd frontend
npm install
cd ..
```

## Required yfinance live-data validation

Leave Upstox disabled or unset for the default validation:

```bash
set MARKET_DATA_PROVIDER=
set UPSTOX_PROVIDER_ENABLED=
```

PowerShell equivalent:

```powershell
Remove-Item Env:MARKET_DATA_PROVIDER -ErrorAction SilentlyContinue
Remove-Item Env:UPSTOX_PROVIDER_ENABLED -ErrorAction SilentlyContinue
```

Start the backend:

```bash
python -m uvicorn api.main:app --reload
```

In another terminal, start the frontend:

```bash
cd frontend
npm run dev
```

Open the local UI:

```text
http://localhost:3000
```

Use at least these real symbols:

```text
SRF.NS
RELIANCE.NS
TCS.NS
```

## Backend endpoint checks

Use the browser or a REST client against the running backend.

Health:

```text
GET http://127.0.0.1:8000/api/health
```

Confirmed compact context:

```text
GET http://127.0.0.1:8000/api/symbols/SRF.NS/decision-context
```

Full confirmed analysis:

```text
GET http://127.0.0.1:8000/api/symbols/SRF.NS/analysis
```

Developing preview:

```text
GET http://127.0.0.1:8000/api/symbols/SRF.NS/decision-context/developing
```

Decision journal evaluations:

```text
GET http://127.0.0.1:8000/api/symbols/SRF.NS/decision-journal/evaluations
```

Data-source diagnostics:

```text
GET http://127.0.0.1:8000/api/symbols/SRF.NS/data-source
```

## Backend acceptance checks

For each real symbol:

- `/api/health` returns successfully.
- `/decision-context` returns `mode=confirmed` or a clear data/error message.
- `/analysis` returns completed weekly bars, evidence, structure, professional score, and embedded `decision_context`.
- `/analysis.decision_context.mode` is `confirmed`.
- `/decision-context/developing` returns `mode=developing` or a clear data/error message.
- `/decision-journal/evaluations` returns `persist_status=false` unless explicitly changed.
- `/data-source` returns diagnostic-only fields and does not trigger a broker/account/order workflow.
- Token values, account identifiers, holdings, funds, margins, positions, and orders are absent from every response.

## Scanner-path acceptance checks

Confirmed analysis should preserve the production scanner path.

Check the code path before validating performance:

```text
api/service.py imports scan_latest_candidate_production
_analyze_symbol_from_weekly(...) calls scan_latest_candidate_production(...)
developing_decision_context_for_symbol(...) is the only API service path that directly uses ScannerEngine().scan_to_index(...)
```

Then validate behavior with real data:

1. Call `/api/symbols/SRF.NS/analysis` once.
2. Confirm a scanner state file is created or refreshed under the local state directory.
3. Call the same endpoint again.
4. Confirm the second call succeeds and does not change the decision semantics unexpectedly.
5. Repeat with `RELIANCE.NS` and `TCS.NS`.

Do not treat runtime speed alone as proof of correctness. Confirmed analysis must continue to use completed weekly bars only.

## Frontend live workflow checks

In the UI, for each test symbol:

1. Enter the symbol and click Analyze.
2. Confirm the VSA Story panel appears.
3. Confirm the story is labeled `Confirmed weekly` by default.
4. Confirm the chart loads and the story stays synchronized with the chart payload.
5. Confirm the data-source panel shows provider/cache status.
6. Confirm cache date range and latest cached date are understandable.
7. Confirm stale-cache warnings, if present, are shown as diagnostics and not as trade signals.
8. Confirm the decision journal panel loads.
9. Confirm journal evaluation display remains read-only by default.
10. Click `Developing preview`.
11. Confirm the view is labeled `Developing preview`.
12. Confirm developing preview does not overwrite the confirmed story.
13. Switch back to `Confirmed weekly`.
14. Confirm the confirmed story remains the default source of truth.
15. Change quickly between symbols and confirm stale responses do not overwrite the active symbol.

## Optional Upstox readiness validation

Only run this section if Upstox credentials and instrument keys are configured locally.

Set environment variables outside the repository:

```bash
set MARKET_DATA_PROVIDER=upstox
set UPSTOX_PROVIDER_ENABLED=true
set UPSTOX_ACCESS_TOKEN_ENV=UPSTOX_ACCESS_TOKEN
set UPSTOX_ACCESS_TOKEN=<token value outside git>
set UPSTOX_SYMBOL_MAP=RELIANCE.NS=NSE_EQ|INE002A01018,TCS.NS=NSE_EQ|INE467B01029
```

Run the readiness helper without a fetch:

```bash
python tools/check_upstox_provider_config.py --symbol RELIANCE.NS
```

Optional read-only fetch check:

```bash
python tools/check_upstox_provider_config.py --symbol RELIANCE.NS --fetch
```

Acceptance checks:

- The helper reports whether Upstox is enabled.
- The helper reports the token environment-variable name.
- The helper reports only token presence, never the token value.
- The helper reports whether the symbol is mapped.
- The optional fetch check performs only a read-only daily OHLCV request.
- No order, position, account, funds, margins, or holdings API is used.

## Failure log template

Record every mismatch before adding more features:

```text
Date/time:
Symbol:
Provider:
Endpoint or UI panel:
Expected:
Actual:
Error text:
Screenshot/log snippet:
Decision impact:
Needs code fix? yes/no
```

## Stop conditions

Stop Milestone 5 feature work and create a focused fix PR if any of these happen:

- Confirmed API analysis directly calls `ScannerEngine().scan_to_index(...)` instead of the production scanner wrapper.
- Confirmed analysis uses a developing/incomplete weekly bar.
- Developing preview is shown as confirmed.
- Developing preview is persisted to confirmed context JSON.
- Journal evaluation mutates saved status without `persist_status=true`.
- Data-source diagnostics downloads market data or refreshes cache.
- Token values or broker account data appear in API/UI output.
- Any order/account/position/holdings/funds/margins scope appears.

## Completion criteria

Phase 0 is complete when:

```text
real yfinance symbols load in the local backend and frontend
confirmed/developing context boundaries are visually clear
journal and provider diagnostics panels work in the live app
scanner production path is verified for confirmed analysis
optional Upstox readiness checks are documented or completed locally
all live mismatches are fixed or logged for focused PRs
```
