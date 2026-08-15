# Project Architecture: Local Python Desktop Finance App (Current State)

## 1. Current System Overview

- The repository is currently a Python-based VSA swing-scanner codebase for market analysis. Despite the project title, the present executable path is a command-line scanner; `gui.py` exists but is empty, so no desktop GUI workflow is currently implemented in the active code.
- `main.py` accepts an optional Yahoo Finance symbol (default `SRF.NS`) and `--limit`, downloads daily OHLCV data, converts it to weekly bars, calculates quantitative metrics, runs the actionable scanner, and prints ranked actionable candidates. 
- Yahoo Finance data is cached locally as CSV files under `cache/`; cached data is reused unless the download function is explicitly called with `refresh=True`.
- The metrics layer is operational for bar geometry, historical rolling statistics, ratios, percentile ranks, and semantic classifications. It deliberately performs quantitative preparation rather than VSA interpretation.
- The market-structure layer currently contains swing detection/history, structural swing scoring, structural progression, trend context, smart-money scoring, and related context models.
- The evidence layer is operational for the currently enabled supply, demand, Stopping Volume, Spring, and structural-progression collection paths, with evidence represented as immutable `Evidence` objects and returned through `EvidenceResult`. Stopping Volume and Spring are collected point-in-time through the demand/evidence production paths.
- Evidence aggregation is operational: evidence is grouped by `(bar_index, direction)`, multiple observations on the same bar/direction are treated as one event, primary/supporting/effort-result/structural roles are separated, and event contribution is calculated without blindly summing duplicate evidence.
- Professional scoring is operational for trend, supply, demand, effort, strength, weakness, and confidence; scanner evaluation combines structural qualification with current/recent directional VSA confirmation.
- The current scanner therefore has a functioning analysis chain from market data through metrics, market structure, evidence, professional scoring, qualification, ranking, and actionable-candidate output.

## 2. Active Python Tech Stack

- **GUI Framework:** PySide6 is declared in `requirements.txt`, and GUI dimensions are present in `config.py`, but `gui.py` is currently empty and `main.py` does not import or initialize a GUI. Therefore no GUI framework is operational in the current execution path.
- **Local Storage Method:** Standard local filesystem CSV cache. `data.py` writes downloaded OHLCV data to `cache/<symbol>.csv` and reads it back with pandas when a cached file exists. Logging is also configured to use `cache/vsa.log`.
- **Calculation/Math Libraries:** pandas is actively used for DataFrames, resampling, rolling/statistical preparation, and analysis; numpy is declared as an active dependency; Python standard-library dataclasses, enums, pathlib, argparse, collections/defaultdict, and related utilities are used throughout. yfinance is the active market-data source. `openpyxl` and `reportlab` are declared dependencies, but the current main execution path does not establish them as active calculation components.
- **Declared dependencies:** PySide6, pandas, numpy, yfinance, openpyxl, reportlab.

## 3. Existing Project File Structure

```text
.
├── .gitignore                         # Repository ignore rules.
├── __init__.py                        # Root package initializer.
├── main.py                            # Current CLI production entry point and actionable scanner output.
├── data.py                            # Yahoo Finance download/cache, validation, and daily-to-weekly conversion.
├── metrics_engine.py                  # Quantitative market-metrics engine.
├── classifiers.py                     # Semantic classifications for direction, volume, spread, and close position.
├── config.py                          # Current application, analysis, VSA, scoring, threshold, and GUI constants.
├── formatters.py                      # Output-formatting helpers.
├── logger.py                          # Logging setup/helpers.
├── models.py                          # Core enums, dataclasses, bar/swing/evidence/context models.
├── scanner.py                          # Scanner candidate model, ranking, qualification, VSA confirmation, and point-in-time scan pipeline.
├── stats_utils.py                     # Statistical helper functions used by metrics/scoring.
├── trend.py                            # Trend/swing analysis and trend result generation.
├── vsa.py                              # Empty module currently.
├── gui.py                              # Empty module currently; no GUI implementation.
├── output.txt                          # Current checked-in diagnostic/output text.
├── requirements.txt                    # Declared Python dependencies.
│
├── background/
│   ├── background_report.py            # Background-report support.
│   ├── confluence.py                   # Background evidence/confluence support.
│   ├── evidence_score.py               # Background evidence scoring support.
│   ├── qualification.py                # Pattern qualification and actionable qualification logic.
│   ├── structural_background.py        # Structural background analysis.
│   └── structural_progression.py       # Structural progression evidence collection.
│
├── cache/
│   ├── ASIANPAINT.NS.csv               # Cached daily OHLCV market data.
│   ├── BHARTIARTL.NS.csv               # Cached daily OHLCV market data.
│   ├── DLF.NS.csv                      # Cached daily OHLCV market data.
│   ├── ETERNAL.NS.csv                  # Cached daily OHLCV market data.
│   ├── HDFCBANK.NS.csv                 # Cached daily OHLCV market data.
│   ├── HINDUNILVR.NS.csv               # Cached daily OHLCV market data.
│   ├── LT.NS.csv                       # Cached daily OHLCV market data.
│   ├── M&M.NS.csv                      # Cached daily OHLCV market data.
│   ├── NTPC.NS.csv                     # Cached daily OHLCV market data.
│   ├── RELIANCE.NS.csv                 # Cached daily OHLCV market data.
│   ├── SBILIFE.NS.csv                  # Cached daily OHLCV market data.
│   ├── SIEMENS.NS.csv                  # Cached daily OHLCV market data.
│   ├── SRF.NS.csv                      # Cached daily OHLCV market data.
│   ├── SUNPHARMA.NS.csv                # Cached daily OHLCV market data.
│   ├── TATASTEEL.NS.csv                # Cached daily OHLCV market data.
│   ├── TCS.NS.csv                      # Cached daily OHLCV market data.
│   ├── TITAN.NS.csv                    # Cached daily OHLCV market data.
│   ├── ULTRACEMCO.NS.csv               # Cached daily OHLCV market data.
│   └── vsa.log                          # Runtime log destination configured by `config.py`.
│
├── Chat summary/
│   ├── Chat Summary 1.md               # Large persisted conversation/recovery summary.
│   ├── Chat Summary 2.md               # Large persisted conversation/recovery summary.
│   └── Chat Summary 3.md               # Large persisted conversation/recovery summary.
│
├── debug/
│   ├── confidence_diagnostics.py       # Confidence diagnostics.
│   ├── diagnose_test.py                # TEST detector diagnostics.
│   ├── diagnose_test_sequence.py       # TEST sequence diagnostics.
│   ├── professional_report.py          # Professional-analysis diagnostic/report support.
│   └── replay.py                        # Replay/debug support for historical scanner behavior.
│
├── diagnose_qualified_event.py         # Qualified-event diagnostic script.
├── diagnose_scanner.py                  # Scanner diagnostic script.
├── diagnose_scanner_ranking.py          # Scanner-ranking diagnostic script.
├── diagnose_structural_invalidation.py  # Structural qualification/invalidation diagnostic script.
│
├── docs/
│   ├── PRIMARY_VSA_EVENT_MATRIX.md      # Current primary-VSA event-role matrix.
│   ├── TEST_EVENT_SPEC.md               # Current TEST event specification.
│   ├── rulebook/
│   │   └── 001_buying_climax.md         # Empty placeholder file currently.
│   └── specifications/
│       └── 001_stopping_volume.md       # Current stopping-volume specification.
│
├── engine/
│   └── columns.py                       # Shared DataFrame column-name definitions.
│
├── evidence/
│   ├── __init__.py                      # Evidence package initializer.
│   ├── aggregator.py                    # Evidence aggregation and event-level contribution logic.
│   ├── campaign.py                      # Campaign detection/support.
│   ├── demand.py                        #  Demand-side evidence collection, including Stopping Volume, Test, Shakeout, and No Supply.
│   ├── effort.py                        # Effort-vs-result evidence collection.
│   ├── engine.py                        # Main EvidenceEngine orchestration and evidence context creation.
│   ├── evidence_registry.py             # Evidence construction/registry mapping.
│   ├── helpers.py                       # Evidence helper functions.
│   ├── patterns..py                     # Empty module currently.
│   ├── phase.py                         # Empty module currently.
│   ├── profiles.py                      # Evidence profiles/supporting definitions.
│   ├── rules.py                         # Low-level evidence rule predicates.
│   ├── scoring.py                       # Evidence scoring helpers.
│   ├── strength.py                      # Evidence-strength support.
│   ├── spring.py                        # Production Spring detection, test validation, confirmation, and conflict-quality adjustment.
│   ├── supply.py                        # Supply-side evidence collection.
│   ├── trend_context.py                 # Trend-context evidence collection.
│   └── weight.py                        # Dynamic evidence-weight calculation.
│
├── market_structure/
│   ├── __init__.py                      # Market-structure package initializer.
│   ├── professional_scorer.py           # Professional structural scoring.
│   ├── progression.py                   # Structural progression determination.
│   ├── smart_money.py                   # Smart-money structural scoring/context.
│   ├── structural_swing_scorer.py       # Professional structural swing scoring.
│   ├── structure_context.py             # Structural context model.
│   ├── structure_filter.py              # Structural filtering.
│   ├── swing_engine.py                  # Confirmed swing detection/confirmation.
│   ├── swing_history.py                 # Historical swing metrics and snapshots.
│   ├── swing_observation.py             # Swing observation model/support.
│   ├── trend_analyzer.py                # Empty module currently.
│   ├── vsa_context.py                   # VSA context construction.
│   └── wyckoff_phase.py                 # Empty module currently.
│
├── model/
│   ├── __init__.py                      # Model package exports.
│   ├── evidence_result_model.py         # Immutable EvidenceResult and evidence query helpers.
│   └── score_model.py                   # Professional scoring result models.
│
├── professional/
│   ├── __init__.py                      # Professional package initializer.
│   ├── score_weights.py                 # Empty module currently.
│   ├── scoring_engine.py                # Professional trend/supply/demand/effort/strength/weakness/confidence scoring.
│   └── scoring_rules.py                 # Empty module currently.
│
├── scripts/
│   └── validate_stopping_volume.py      # Stopping-volume validation utility.
│
├── smart_money/
│   ├── __init__.py                      # Smart-money package initializer.
│   ├── base_percentile.py               # Smart-money percentile helper/base.
│   ├── base_rule.py                     # Smart-money rule base.
│   ├── evidence_engine.py               # Empty module currently.
│   ├── evidence_registry.py             # Smart-money evidence registry.
│   ├── evidence_rule.py                 # Smart-money evidence-rule base.
│   └── rules/
│       ├── __init__.py                  # Smart-money rules package initializer.
│       ├── absorption.py                # Empty rule module currently.
│       ├── accumulation.py              # Empty rule module currently.
│       ├── buying_climax.py             # Empty rule module currently.
│       ├── distribution.py              # Empty rule module currently.
│       ├── effort_vs_result.py           # Empty rule module currently.
│       ├── no_demand.py                 # Empty rule module currently.
│       ├── no_supply.py                 # Empty rule module currently.
│       ├── selling_climax.py            # Empty rule module currently.
│       ├── shakeout.py                  # Empty rule module currently.
│       ├── spring.py                    # Empty rule module currently.
│       ├── stopping_volume.py           # Implemented stopping-volume rule module; production semantics validated point-in-time.
│       ├── test.py                      # Empty rule module currently.
│       └── upthrust.py                  # Empty rule module currently.
│
├── tests/
│   ├── test_demand_detectors.py         # Tests demand-side detectors.
│   ├── test_no_supply_scoring_role.py   # Tests no-supply scoring role.
│   ├── test_primary_vsa_event_matrix.py # Tests primary VSA event-role matrix.
│   ├── test_qualification.py            # Tests qualification behavior.
│   ├── test_scanner_actionable.py       # Tests actionable scanner behavior.
│   ├── test_scanner_current_actionable.py # Tests current actionable scanner behavior.
│   └── test_scanner_latest_bar_regression.py # Regression test for latest-bar scanner behavior.
│
├── tools/
│   ├── audit_anchor_incremental_value.py       # Audit of anchor incremental value.
│   ├── audit_anchor_support_by_trend_state.py  # Audit of anchor support by trend state.
│   ├── audit_clamp_outcomes.py                 # Audit of clamp outcomes.
│   ├── audit_conditional_weight_effectiveness.py # Audit of conditional weight effectiveness.
│   ├── audit_event_combinations.py              # Audit of evidence-event combinations.
│   ├── audit_event_incremental_value.py         # Audit of incremental event value.
│   ├── audit_event_specific_weight_calibration.py # Audit of event-specific weight calibration.
│   ├── audit_trend_cases.py                     # Audit of trend cases.
│   ├── audit_trend_counterfactual_outcomes.py   # Audit of trend counterfactual outcomes.
│   ├── audit_trend_outcomes.py                  # Audit of trend outcomes.
│   ├── audit_trend_weight_counterfactual.py     # Audit of trend-weight counterfactuals.
│   ├── audit_weight_bucket_effectiveness.py     # Audit of weight-bucket effectiveness.
│   ├── audit_weight_calibration_stability.py    # Audit of weight-calibration stability.
│   ├── audit_weight_clamp.py                    # Audit of weight clamping.
│   ├── audit_weight_incremental_effects.py      # Audit of incremental weight effects.
│   ├── audit_weight_structure_trend_effectiveness.py # Audit of structure/trend weight effectiveness.
│   ├── check_clamp_join.py                      # Clamp/join diagnostic check.
│   ├── historical_validation.py                 # Historical validation utility.
│   └── inventory_evidence_model.py              # Evidence-model inventory/audit utility.
│
├── utils/
│   ├── ranking.py                      # Ranking helper.
│   └── scoring.py                      # Score components, score bands, and score-combination utilities.
│
└── wyckoff/
    ├── __init__.py                    # Wyckoff package initializer.
    ├── engine.py                       # Wyckoff engine implementation.
    └── wyckoff_model.py                # Wyckoff model definitions.
```

The tree above reflects the repository's current `main` tree; empty files are intentionally identified as empty rather than being treated as implemented architecture.

## 4. Completed Functional Workflows

### App Launch & UI Initialization

1. `main.py` starts as the production entry point.
2. `argparse` reads an optional symbol and `--limit`; the default symbol is `SRF.NS` and the default limit is 10.
3. The symbol is passed to `download_data()`.
4. `download_data()` first checks `cache/<symbol>.csv`; if present and `refresh=False`, it loads that CSV instead of downloading again.
5. Otherwise yfinance downloads daily data with `period="max"`, `interval="1d"`, and `auto_adjust=False`.
6. yfinance MultiIndex columns are flattened when necessary, only Open/High/Low/Close/Volume are retained, names are standardized to lowercase, dates are normalized/sorted, and an incomplete latest row is removed if it contains NaNs.
7. The daily dataset is validated and cached.
8. `daily_to_weekly()` resamples with `W-FRI`, using first Open, maximum High, minimum Low, last Close, and summed Volume; it also records the first trading day of each weekly group as `week_beginning`.
9. `MetricsEngine.calculate()` creates quantitative metrics and semantic classifications.
10. `ScannerEngine.scan_actionable(metrics)` runs the point-in-time scanner over the metric history and ranks actionable candidates.
11. `main.py` prints the ranked candidates, including symbol, bar index/week, qualification, actionability, scores, confidence, target/campaign/qualifying/scoring evidence codes, and scoring-bar information.

No GUI initialization occurs in this workflow. The declared PySide6 dependency and GUI dimensions are present, but `gui.py` is empty and is not imported by `main.py`.

### Current Data Handling

- Input is daily OHLCV data from Yahoo Finance.
- Cache files are plain CSVs with the standardized fields `open`, `high`, `low`, `close`, and `volume`, indexed by date when loaded.
- Weekly conversion produces `week_beginning`, `open`, `high`, `low`, `close`, and `volume`.
- Metrics add quantitative geometry and historical normalization, including spread, body, upper/lower shadows, close ratio, previous-bar values, price change, price-change percentage, rolling average volume/spread, rolling standard deviations, volume/spread ratios, historical percentiles, and semantic spread/volume/direction/close-position classifications.
- Historical percentile and rolling calculations are deliberately based on prior history rather than the current bar to avoid look-ahead bias.
- Evidence is collected from a `BackgroundContext` built from the recent/background metric windows, trend structure, structural swings, structural pattern, and VSA context.
- Evidence is stored as immutable records and grouped by `(bar_index, direction)` by the aggregator so multiple evidence codes on the same bar/direction become one aggregated market event.
- Primary VSA evidence is treated as the anchor contribution; supporting, effort/result, and structural evidence modify the event rather than simply stacking all weights independently.
- Current configured primary VSA codes include buying climax, selling climax, upthrust, shakeout, spring, and test; supporting codes include supply/demand observations such as supply coming in, increasing supply, hidden supply/demand, supply/demand drying up, stopping volume, no-supply, and no-demand; effort/result and structural progression have their own roles.
- Professional scoring converts trend/supply/demand/effort information into normalized strength, weakness, and confidence measures and returns a `ProfessionalScoreResult`.
- Scanner qualification requires persistent structural qualification plus sufficiently fresh directional VSA confirmation; the scanner can invalidate stale qualification, missing VSA confirmation, stale VSA confirmation, or contradictory VSA pressure.

## 5. Current Data Models / File Schema

### Market-data CSV schema

The active cache schema is:

```text
date index
open
high
low
close
volume
```

### Weekly DataFrame schema

```text
week_beginning
open
high
low
close
volume
```

### Metrics DataFrame fields currently generated

The active metrics engine creates/uses the following field families:

```text
open, high, low, close, volume
spread
body
upper_shadow
lower_shadow
close_ratio
prev_high
prev_low
prev_close
prev_spread
price_change
price_change_pct
avg_volume
avg_spread
std_volume
std_spread
volume_ratio
spread_ratio
spread_percentile
volume_percentile
spread_class
volume_class
direction
close_position
week_beginning
```

### Core semantic enums/models

- `Direction`: DOWN=-1, NEUTRAL=0, UP=1.
- `VolumeClass`: ULTRA_LOW, VERY_LOW, LOW, AVERAGE, HIGH, VERY_HIGH, ULTRA_HIGH.
- `SpreadClass`: NARROW, BELOW_AVERAGE, AVERAGE, ABOVE_AVERAGE, WIDE, VERY_WIDE.
- `ClosePosition`: ON_LOW=0, LOWER=1, MIDDLE=2, UPPER=3, ON_HIGH=4.
- `EvidenceCategory`: SUPPLY, DEMAND, EFFORT, TREND, PHASE, VOLUME, SPREAD, SIGNAL, RESULT, ABSORPTION, EXHAUSTION, CONTINUATION, TRAP.
- `EvidenceDirection`: BULLISH=1, NEUTRAL=0, BEARISH=-1.
- `EvidenceCode`: current atomic codes include BUYING_CLIMAX, SUPPLY_COMING_IN, INCREASING_SUPPLY, HIDDEN_SUPPLY, SUPPLY_DRYING_UP, SUPPLY_HIGH_VOLUME, SUPPLY_WIDE_SPREAD, SUPPLY_ABSORPTION, STOPPING_VOLUME, DEMAND_COMING_IN, INCREASING_DEMAND, HIDDEN_DEMAND, DEMAND_DRYING_UP, NO_SUPPLY, EFFORT_GT_RESULT, RESULT_GT_EFFORT, ABSORPTION, STRONG_UPTREND, WEAK_UPTREND, STRONG_DOWNTREND, WEAK_DOWNTREND, SIDEWAYS_MARKET, ACCUMULATION, REACCUMULATION, MARKUP, DISTRIBUTION, REDISTRIBUTION, MARKDOWN, SPRING, UPTHRUST, TEST, NO_DEMAND, SELLING_CLIMAX, EFFORT_RESULT, SHAKEOUT, STRUCTURAL_PROGRESSION_IMPROVING, and STRUCTURAL_PROGRESSION_WEAKENING.
- `TrendDirection`: UNKNOWN, UP, DOWN, RANGE.
- `TrendState`: UNKNOWN, DEVELOPING, HEALTHY, CORRECTING, EXHAUSTED, REVERSING.
- `MarketBias`: BULLISH, BEARISH, NEUTRAL.
- `Swing`: confirmed swing type/price/pivot/confirmation/week/metrics index.
- `ClassifiedSwing`: a confirmed swing plus HH/HL/LH/LL classification.
- `StructuralSwing`: a swing plus professional evaluation, grade, and failure flag.
- `TrendStructure`: direction, state, strength, confidence, swing counts, classified swings, structural swings, and HH/HL/LH/LL counts.
- `EvidenceResult`: immutable `context` plus an immutable tuple of `Evidence` with supply/demand/trend/strength/weakness/category/code query helpers.
- `ScannerCandidate`: immutable combination of evidence, professional score, qualification result, target-bar evidence, campaign evidence, qualifying evidence, scoring evidence, scoring-bar metadata, and actionability properties.

### Evidence event aggregation

Evidence is grouped by `(bar_index, EvidenceDirection)`. Each group stores all codes on that bar/direction. The current event contribution model is:

- If a primary event exists, the strongest primary contribution is the anchor; supporting evidence modifies it by 15%, effort/result by 15%, and structural context by 10%.
- If no primary event exists, supporting evidence contributes at 60%, effort/result at 25%, and structural context at 15%.
- Event contribution is capped by the configured maximum combined event contribution of 1.50.
- Current primary VSA codes include BUYING_CLIMAX, SELLING_CLIMAX, UPTHRUST, SHAKEOUT, SPRING, TEST, and STOPPING_VOLUME where the corresponding detector logic is production-enabled. Supporting codes include supply/demand observations such as supply coming in, increasing supply, hidden supply/demand, supply/demand drying up, no-supply, and no-demand; effort/result and structural progression have their own roles.

### Shakeout recovery data currently used

The implemented recovery validation stores:

```text
test/reference low
 test/reference close
 test/reference spread
 test/reference volume
recovery_index
spread_ratio
volume_ratio
close_position
close_change_ratio
low_distance_from_test
```

The recovery quality calculation currently averages five normalized components: close position, close-change quality, low-hold quality, spread quality, and volume quality. The current configuration includes a recovery lookahead of 5 bars, minimum recovery close position 3, spread target 0.75, volume target 0.75, close-change target 0.10, and low-clearance target 0.25.

### INCREASING_DEMAND Calibration Record

INCREASING_DEMAND is provisionally registered at a production weight of 0.85.

Validation:
- 902 point-in-time events across 8 symbols.
- POSITIVE_8_BAR: 464
- NEGATIVE_8_BAR: 303
- FLAT_8_BAR: 135
- Beneficial decision changes: 26
- Harmful decision changes: 15
- Net benefit: +11
- Benefit/harm ratio: 1.7333
- Leave-one-symbol-out validation remained positive for all 8 exclusions.
- Minimum leave-one-symbol-out net benefit: +6.
- Minimum leave-one-symbol-out benefit/harm ratio: 1.4286.

The result is not dependent on a single symbol. Excluding either RELIANCE.NS or TCS.NS still produced a net benefit of +6.
The 0.85 weight is provisional and should be recalibrated when the validation universe or historical sample expands materially.

### Stopping Volume production record

`STOPPING_VOLUME` is a production-integrated primary demand-side VSA event.

Mandatory point-in-time requirements:

1. Selling Campaign.
2. Bearish current bar.
3. High VSA volume or higher.
4. Above-average spread.
5. Close off the low.

Non-mandatory confirmations:

- Very-high volume.
- Wide spread.
- Increasing volume.
- Higher low.

The detector intentionally allows imperfect real-market examples rather than requiring textbook-perfect bar geometry.
Point-in-time validation across the eight-symbol validation universe produced:

- 59 events.
- 39 positive 8-bar outcomes.
- 14 negative 8-bar outcomes.
- 6 flat outcomes.
- 53 decisive outcomes.
- 73.58% positive decisive rate.
- 8/8 symbols with events.
- 0 replay failures.

Leave-one-symbol-out validation remained between 68.29% and 80.43% positive decisive rate.
The production evidence weight remains 1.00. No weight optimization was promoted.

### Calibration Promotion Rule

An evidence detector should not be promoted to production solely because it produces historical events.
The standard promotion sequence is:

1. Point-in-time historical replay.
2. Outcome classification.
3. Candidate-weight calibration.
4. Outcome-level attribution.
5. Symbol-level robustness analysis.
6. Leave-one-symbol-out validation.
7. Provisional production registration.
8. Later recalibration as the validation universe expands.

`INCREASING_DEMAND` has completed this sequence and is therefore registered provisionally at weight `0.85`.

## 6. Current Implementation Details

### Fully coded and currently used

- Yahoo Finance daily data acquisition and local CSV caching.
- Daily OHLCV validation and incomplete-latest-bar removal.
- Daily-to-weekly OHLCV resampling.
- Quantitative metrics, historical rolling statistics, percentile normalization, and semantic bar classification.
- Confirmed swing detection, swing history, HH/HL/LH/LL classification, structural swing scoring, structural progression, trend direction/state/strength/confidence, and VSA context construction.
- EvidenceEngine context construction and active supply, demand, Spring, and structural-progression collection paths.
- Evidence construction through the evidence registry and dynamic evidence weights.
- Active VSA detectors represented in the current evidence code/configuration, including supply observations, demand observations, stopping volume, upthrust, buying climax, shakeout, Spring, TEST, and structural progression codes where corresponding detector logic is present. Spring uses point-in-time candidate/test/confirmation validation, has a provisional production weight of 0.75, and retains the event while reducing evidence quality to 0.50 when the same bar also emits UPTHRUST or BUYING_CLIMAX.
- Shakeout validation/recovery scoring is implemented, including the five-component recovery-quality calculation and combined shakeout quality.
- Event-level evidence aggregation by bar/direction, primary/supporting/effort-result/structural role separation, combined-event contribution calculation, and bullish/bearish/neutral bias calculation.
- Professional scoring of trend, supply, demand, effort, strength, weakness, and confidence.
- Pattern qualification and scanner invalidation/continuation logic for structural persistence and fresh directional VSA confirmation.
- Actionable candidate ranking and CLI reporting.
- A substantial test suite and a collection of diagnostic/audit scripts are present and used as development/validation tooling.

### Present but empty or intentionally inactive in the current tree

- `gui.py` is empty; there is no implemented desktop GUI workflow in the current main execution path.
- `vsa.py` is empty.
- `market_structure/trend_analyzer.py` is empty; the active trend implementation is currently in `trend.py`.
- `market_structure/wyckoff_phase.py` is empty.
- `evidence/patterns..py` is empty.
- `evidence/phase.py` is empty.
- `professional/score_weights.py` is empty.
- `professional/scoring_rules.py` is empty.
- `smart_money/evidence_engine.py` is empty.
- Most files under `smart_money/rules/` are currently empty; `smart_money/rules/stopping_volume.py` is the implemented exception visible in the current tree.
- `docs/rulebook/001_buying_climax.md` is empty.
- Several collection calls in `EvidenceEngine.collect()` remain commented out, including separate `_collect_effort()`, `_collect_trend()`, `_collect_phase()`, and several detector-specific calls; the active orchestration currently calls supply, demand, and structural progression.

### Current implementation boundary

The checked-in code is therefore a functioning research/analysis scanner with an evidence-driven VSA pipeline and local cached market data, not yet a completed GUI desktop application. This document intentionally records that current boundary rather than inventing a future architecture or treating empty modules/comments as implemented features.
