# Milestone 4 Decision-Support Roadmap

## Status

Milestone 4 is the transition from a validated scanner/audit engine into a local
professional decision-support terminal.

The product direction is not a hosted SaaS platform and not an auto-trading bot.
ProVSA is intended to run on the user's local computer, use real market data when
available, explain VSA/Wyckoff context bar by bar, and help the trader make a
human discretionary decision.

The calibration proposal layer added in `audit.proposals` remains useful, but it
is a supporting research track. The main Milestone 4 product track is compact
VSA decision context, VSA Story, FastAPI integration, and frontend presentation.

## Product boundary

ProVSA must remain a decision-support tool.

It must not:

- place trades;
- manage orders;
- auto-execute entries or exits;
- require broker order permissions;
- treat analysis output as financial advice;
- confirm weekly VSA signals from incomplete weekly bars.

Future broker integrations, such as Upstox, should be introduced as read-only
market-data providers unless a later explicit product decision changes that
scope. The near-term system should request and use market data only.

## Local-first deployment model

The expected operating model is:

```text
Local computer
  -> local market-data/cache layer
  -> local FastAPI backend
  -> local React/Next.js frontend
  -> Lightweight Charts visual decision workspace
```

Hosting is not a requirement. A future installer/executable is desirable after
the local workflow stabilizes.

Potential future packaging paths:

```text
Local launcher
  - starts FastAPI
  - serves or starts the frontend
  - opens localhost in the browser

Desktop wrapper
  - Tauri or Electron shell
  - local backend process
  - bundled frontend UI

Backend executable
  - PyInstaller or Nuitka backend package
  - static frontend build served locally
```

Packaging is deliberately later than decision-context and story correctness.

## Current foundation

Already available foundations:

```text
- Daily data cache with Parquet preferred and CSV fallback.
- Incremental recent data refresh.
- Completed weekly bar filtering.
- Production scanner state persistence per symbol/timeframe.
- Incremental production scanner path for latest-bar scans.
- Live scanner skip logic when source data has not changed.
- Bounded parallel live symbol scanning.
- FastAPI REST API foundation.
- React/Next.js frontend foundation.
- Lightweight Charts visualization foundation.
- Milestone 3 audit outputs and calibration summaries.
- Calibration proposal CSV framework.
```

Important current gap:

```text
The FastAPI analysis endpoint should be moved away from direct full point-in-time
scanner evaluation and toward the optimized production/incremental path.
```

## Persistence principle

Do not store the full historical VSA event stream merely to render the local app.

Store only enough compact intelligence to make the current decision:

```text
- symbol and timeframe;
- latest completed bar identity;
- latest scanner candidate/qualification summary;
- recent important VSA events;
- recent important structural swings;
- current supply/demand bias;
- current phase hypothesis;
- tradability status;
- VSA Story summary;
- confirmation condition;
- invalidation condition;
- what to expect next;
- last scanned/updated timestamp.
```

This is a trader decision memory, not an audit warehouse.

A compact context should answer:

```text
What phase is the stock likely in?
What did Smart Money appear to do recently?
Is the setup tradable now, waitlist-only, or avoid?
What confirmation should improve the case?
What invalidation would weaken the case?
What should the trader expect next?
```

## Confirmed vs developing mode

The scanner should separate confirmed decisions from developing observations.

Confirmed mode:

```text
- uses only completed weekly bars;
- drives official qualification and tradability status;
- is the source of record for decision context;
- should be stable across repeated local app refreshes.
```

Developing mode:

```text
- may inspect the current unfinished daily/weekly bar;
- is early warning only;
- must not overwrite the confirmed decision state;
- should be labelled clearly as developing/incomplete;
- can help the trader prepare scenarios before weekly close.
```

This distinction is critical for avoiding look-ahead bias and unfinished-candle
false confidence.

## VSA Story objective

The front-facing output should explain the sequence of Smart Money activity
instead of listing isolated event codes.

The VSA Story should describe:

```text
- what happened bar by bar or phase by phase;
- whether supply increased, disappeared, or was absorbed;
- whether demand appeared, failed, or confirmed strength;
- how structural swings changed the context;
- whether the stock looks tradable now or needs confirmation;
- what the trader should watch next.
```

Example style:

```text
Weeks 1-2: Heavy selling appeared, but wide volume with limited downside progress
suggested possible professional absorption rather than clean markdown.

Week 3: A test appeared after weakness, suggesting supply may be drying up.

Week 4: Demand returned near the current structure, improving the accumulation
case.

Current: The stock remains constructive, but the best decision is to wait for a
controlled pullback or fresh confirmation before treating it as tradable.
```

The narrative should be deterministic, sourced from scanner outputs, and safe to
show in the local UI.

## Tradability labels

Suggested initial labels:

```text
tradable_now
wait_for_pullback
wait_for_confirmation
watchlist_only
observation_only
avoid
uncertain
```

These are decision-support labels, not trade instructions.

Each label should be accompanied by:

```text
- reason;
- confidence;
- confirmation condition;
- invalidation condition;
- risk note;
- relevant evidence/event codes;
- relevant bar indices/weeks.
```

## Market-data approach

Use real market data for manual/live validation, but keep deterministic fixtures
for automated tests.

Recommended order:

```text
1. Continue using the existing yfinance/cache path for baseline local operation.
2. Add a provider interface before adding broker-specific logic.
3. Later add Upstox as a read-only market-data provider if needed.
4. Keep order placement out of scope.
```

Provider shape:

```text
MarketDataProvider
  - CachedDataProvider
  - YFinanceProvider
  - Future: UpstoxMarketDataProvider
  - Future: NSE-authorized vendor provider
```

Live data should be used to validate real market scenarios:

```text
scanner expectation
  -> next completed bar
  -> confirmation or invalidation
  -> journal/review
  -> possible model improvement
```

Production logic should not be changed directly from one or two live examples.
Use live observations to find hypotheses, then validate with broader audit data.

## Calibration proposal layer

`audit.proposals` remains analysis-only. It converts Milestone 3 summary outputs
into reviewable CSVs for future strategy changes.

It must not:

- change detector logic;
- change scoring weights;
- change scanner thresholds;
- change ranking, qualification, or actionability;
- change API or live scanner behavior;
- write production configuration files.

Any production strategy update must happen in a later explicit PR with supporting
proposal rows, live observations, and before/after audit evidence.

Default proposal actions:

```text
review_for_weight_increase
review_for_weight_decrease
review_for_monitoring
collect_more_data
keep_current
```

These are review recommendations only.

## Milestone 4 to-do list

### Track A: local decision context

1. Add compact `DecisionContext` models.
2. Add JSON persistence under `state/context/`.
3. Store only recent relevant evidence, structure, phase, tradability, and story
   summary.
4. Add schema versioning and safe identity filenames.
5. Add tests for empty/missing/corrupt context files.

### Track B: VSA Story engine

1. Build deterministic story segments from recent evidence and structural swings.
2. Add phase hypothesis labels such as accumulation, markup, distribution,
   markdown, re-accumulation, and uncertain.
3. Add supply/demand bias summary.
4. Add `what_to_expect_next`, confirmation, and invalidation text.
5. Add tests for common VSA sequences:
   - stopping volume -> test -> demand;
   - shakeout -> recovery;
   - upthrust/no demand -> weakness;
   - absorption without confirmation;
   - conflicting evidence.

### Track C: FastAPI integration

1. Move `/api/symbols/{symbol}/analysis` toward the production incremental path.
2. Add decision-context fields to API schemas.
3. Return cached decision context instantly when no new completed bar exists.
4. Add explicit response fields for confirmed versus developing state.
5. Add API tests for success, invalid symbol, empty bars, and cached context.

### Track D: frontend decision workspace

1. Add a VSA Story panel.
2. Link story segments to chart markers and bar indices.
3. Show tradability as decision-support status, not an order recommendation.
4. Show confirmation/invalidation conditions.
5. Add developing-bar warning when viewing incomplete data.

### Track E: live validation journal

1. Save each confirmed decision snapshot when a new completed bar appears.
2. Store expected next behavior compactly.
3. Compare later bars against prior expectation.
4. Mark confirmed, invalidated, or still pending.
5. Use this journal to discover faulty assumptions and candidates for later audit.

### Track F: market-data providers

1. Define a provider interface.
2. Keep yfinance/cache as the default local provider.
3. Add Upstox read-only provider later if needed.
4. Keep broker order placement out of scope.
5. Keep provider credentials outside the repository.

### Track G: packaging later

1. Stabilize local backend/frontend workflow first.
2. Add a local launcher script.
3. Bundle static frontend after API contracts settle.
4. Evaluate PyInstaller/Nuitka plus Tauri/Electron options.
5. Produce an installer only after scanner/story/API behavior is stable.

## Recommended next PR sequence

```text
PR #38: Add compact VSA decision context persistence
PR #39: Add VSA Story engine foundation
PR #40: Expose decision context and story through FastAPI
PR #41: Make FastAPI use the production incremental scanner path
PR #42: Add VSA Story panel to React/Next.js frontend
PR #43: Add confirmed/developing mode UI separation
PR #44: Add live validation journal
PR #45: Add market-data provider interface
PR #46: Add optional Upstox read-only market-data provider
PR #47: Add local launcher/packaging foundation
```

The exact order may change if a dependency is discovered, but production scoring
changes should stay behind decision-context, story, and validation work.

## Milestone 4 success criteria

Milestone 4 is successful when the local app can:

```text
- load a symbol quickly without unnecessary full historical scanner loops;
- show the latest confirmed VSA decision context;
- explain the recent Smart Money story in plain language;
- mark whether the setup is tradable, watchlist-only, or avoid;
- explain what should happen next;
- explain what would invalidate the thesis;
- preserve enough local memory to avoid recalculating unchanged decisions;
- use real market data for manual validation;
- keep tests deterministic with fixtures;
- remain strictly decision-support, not auto-trading.
```
