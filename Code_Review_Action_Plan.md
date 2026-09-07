# ProVSA Code Review Action Plan

Repository: https://github.com/retnakalakjm-creator/ProVSA  
Review date: 2026-09-07  
Purpose: Read-only action notes for improving the Stock Market Swing Scanner step by step.

---

## Priority 1 — Execution Logic & Financial Math

### 1. Enforce completed weekly bars only

**Issue:** `daily_to_weekly()` can include the currently forming weekly candle. Live scanning may therefore evaluate incomplete weekly OHLCV data.

**Risk:** Look-ahead-like live behavior and unstable weekly signals.

**Action:** Add a `completed_weekly_only()` function and call it before `MetricsEngine().calculate(weekly)`.

**Suggested rule:**

```python
def completed_weekly_only(weekly, now=None):
    # Drop the latest weekly bar if the current week has not closed.
    ...
```

**Files likely affected:**

- `data.py`
- `live_scanner.py`
- `main.py`
- Tests for weekly bar completion

---

### 2. Separate signal bar from execution bar

**Issue:** Scanner output reports the signal week/bar but does not clearly define when a trade is executable.

**Risk:** Backtests may accidentally enter on the same close that generated the signal.

**Action:** Add a model such as `SignalEvent` with:

- `signal_index`
- `signal_week`
- `signal_known_at`
- `execution_index`
- `execution_rule`
- `side`
- `score`
- `confidence`

**Rule:** A weekly signal should usually be tradable only from the next bar after confirmation.

**Files likely affected:**

- `scanner.py`
- `live_scanner.py`
- Any future backtest module

---

### 3. Display both pivot week and confirmation week for swings

**Issue:** Swing objects track both `bar_index` and `confirmation_index`, but scanner/report output can make users think the swing was known at the pivot.

**Risk:** Misleading interpretation of signals.

**Action:** In candidate output, show:

- Pivot week
- Confirmation week
- Tradable-from week/date

**Files likely affected:**

- `main.py`
- `live_scanner.py`
- Reporting/export modules

---

### 4. Rename Spring “lookahead” constants

**Issue:** Spring detection appears causal, but internal constant names like lookahead can make the logic look biased.

**Action:** Rename to clearer causal terms:

- `_CONFIRMATION_WINDOW_BARS`
- `_TEST_SEARCH_WINDOW_BARS`
- `_PRODUCTION_CANDIDATE_LOOKBACK`

**Files likely affected:**

- `evidence/spring.py`
- Spring tests

---

## Priority 2 — Data Pipeline Efficiency

### 5. Replace routine `period="max"` with a configurable production lookback

**Issue:** `DEFAULT_PERIOD = "max"` is expensive for regular scans.

**Action:** Use a configurable value such as:

```python
DEFAULT_PERIOD = "10y"
```

Keep `max` only for research/backfill mode.

**Files likely affected:**

- `config.py`
- `data.py`

---

### 6. Replace CSV cache with Parquet plus metadata

**Issue:** CSV is slower, larger, and weaker for schema preservation.

**Action:** Cache as:

```text
cache/yfinance/<symbol>/1d.parquet
cache/yfinance/<symbol>/metadata.json
```

Metadata should include:

- symbol
- provider
- interval
- auto-adjust mode
- first date
- last date
- last refresh UTC
- schema version

**Files likely affected:**

- `data.py`
- Tests for cache read/write

---

### 7. Surface stale-cache warnings

**Issue:** If recent refresh fails, the code silently falls back to cached data.

**Risk:** User may believe the scan used fresh data.

**Action:** Return a structured data result:

```python
@dataclass(frozen=True)
class DataResult:
    symbol: str
    data: pd.DataFrame
    source: str  # fresh, cache, stale_cache
    last_refresh_utc: datetime
    warning: str | None = None
```

**Files likely affected:**

- `data.py`
- `main.py`
- `live_scanner.py`

---

### 8. Add corporate-action anomaly handling

**Issue:** `auto_adjust=False` can allow splits/bonus events to distort spread, trend, and swing detection.

**Action:** Add corporate-action or extreme-gap detection.

Possible first rule:

```python
def detect_corporate_action_anomaly(df):
    raw_gap = df["close"].pct_change().abs()
    return raw_gap > 0.35
```

Suppress or downweight signals around flagged bars.

**Files likely affected:**

- `data.py`
- `metrics_engine.py`
- Scanner/evidence scoring rules

---

### 9. Remove committed cache data from Git tracking

**Issue:** `.gitignore` ignores `cache/`, but cached CSV files appear to be present in the repository history/tree.

**Action:** Run:

```bash
git rm -r --cached cache
git rm --cached "*.csv"
```

Then commit the cleanup.

**Files likely affected:**

- Git index
- Repository hygiene only

---

## Priority 3 — Performance & Bottlenecks

### 10. Make incremental scanning the production path

**Issue:** `ScannerEngine.scan_actionable()` still rebuilds expanding history up to the latest bar.

**Risk:** O(n²)-style behavior per symbol.

**Action:** Promote `IncrementalScannerEngine` and `ScannerStateStore` as the default live/production path.

**Target flow:**

```text
load data
calculate metrics
load scanner state
resume latest scan
save scanner state
return candidate/signal
```

**Files likely affected:**

- `main.py`
- `live_scanner.py`
- `incremental_scanner.py`
- `scanner_state.py`

---

### 11. Avoid repeated object creation inside replay loops

**Issue:** Replay loops repeatedly instantiate `TrendAnalyzer()` and `EvidenceEngine()`.

**Action:** Reuse objects where safe, or expose incremental APIs.

**Files likely affected:**

- `scanner.py`
- `trend.py`
- `evidence/engine.py`

---

### 12. Parallelize by symbol

**Issue:** Multi-symbol scanning is currently sequential.

**Action:** Use:

- Thread pool for downloads
- Process pool for CPU-heavy scanning

**Suggested pattern:**

```python
with ProcessPoolExecutor(max_workers=os.cpu_count() - 1) as pool:
    results = list(pool.map(scan_one_symbol, symbols))
```

**Files likely affected:**

- `live_scanner.py`
- New `universe_scanner.py` or similar

---

### 13. Keep rich dataclasses out of the hot path

**Issue:** Many `Evidence`, `Swing`, `ScoreBreakdown`, and context objects are created during repeated scans.

**Action:** Use arrays/integer codes/floats in the hot path. Create dataclasses only for final selected candidates or diagnostics.

**Files likely affected:**

- `evidence/`
- `market_structure/`
- `professional/`
- `scanner.py`

---

### 14. Make profiling optional

**Issue:** `line_profiler.profile` is imported in production modules.

**Action:** Either remove profiling decorators from production code or wrap them safely:

```python
try:
    from line_profiler import profile
except ImportError:
    def profile(func):
        return func
```

**Files likely affected:**

- `market_structure/structure_filter.py`
- `market_structure/professional_scorer.py`
- `market_structure/smart_money.py`
- `requirements.txt`

---

## Priority 4 — Code Architecture & Cleanliness

### 15. Split the large config file

**Issue:** `config.py` mixes app paths, trend settings, VSA thresholds, scoring weights, Wyckoff settings, and debug flags.

**Action:** Split into typed settings modules:

```text
settings/app.py
settings/data.py
settings/trend.py
settings/vsa.py
settings/smart_money.py
settings/structure.py
settings/scoring.py
```

Or use dataclasses such as:

```python
@dataclass(frozen=True)
class TrendSettings:
    recent_swings: int = 8
    direction_margin: float = 0.20
    state_lookback: int = 4
```

**Files likely affected:**

- `config.py`
- All modules importing `config`

---

### 16. Remove or move placeholder/unfinished files

**Issue:** Several modules appear to be placeholders or experiments.

**Action:** Move unfinished code to:

```text
experiments/
archive/
docs/design/
```

Keep production packages importable and clean.

---

### 17. Fix `StructureFilter._grade_swing()`

**Issue:** `_grade_swing()` always returns `SwingGrade.MAJOR`, making grade meaningless.

**Action:** Implement score-based grading:

```python
def _grade_swing(self, score: float) -> SwingGrade:
    if score >= 0.80:
        return SwingGrade.MAJOR
    if score >= 0.65:
        return SwingGrade.INTERMEDIATE
    return SwingGrade.MINOR
```

**Files likely affected:**

- `market_structure/structure_filter.py`
- Related tests

---

### 18. Replace private method access with public APIs

**Issue:** `incremental_scanner.py` accesses private `TrendAnalyzer` internals such as `_reset`, `_swing_engine`, `_classified_swings`, `_create_structure`, and `_build_result`.

**Action:** Add a public method:

```python
class TrendAnalyzer:
    def analyze_from_state(self, metrics, state):
        ...
```

**Files likely affected:**

- `trend.py`
- `incremental_scanner.py`

---

### 19. Improve error types

**Issue:** Broad `except Exception` in data refresh hides details.

**Action:** Add typed exceptions:

```python
class DataRefreshError(RuntimeError):
    pass

class DataValidationError(ValueError):
    pass
```

Also log or return refresh failure details.

**Files likely affected:**

- `data.py`
- `logger.py`
- CLI/API output

---

## Suggested Work Order

1. Enforce completed weekly bars only.
2. Add signal/execution separation.
3. Remove committed cache files from Git.
4. Add stale-cache warning output.
5. Fix `StructureFilter._grade_swing()`.
6. Make profiling optional.
7. Promote incremental scanner to production live path.
8. Replace CSV cache with Parquet metadata cache.
9. Add corporate-action anomaly flags.
10. Split `config.py` into typed settings modules.
11. Add symbol-level parallel scanning.
12. Move placeholder/experimental code out of production packages.

---

## Definition of Done for Production Readiness

The scanner should be considered stronger when it satisfies all of the following:

- Latest weekly bar is used only after it closes.
- Every signal has a known execution rule.
- No signal uses evidence from bars after the signal-known time.
- Cached data freshness is visible to the user.
- Corporate-action weeks are flagged or suppressed.
- Incremental scanner output matches full replay output in tests.
- Multi-symbol scanning runs without O(n²) replay per symbol.
- Config is typed, grouped, and easy to audit.
- Production code does not depend on profiling tools.
- Repository does not contain generated cache data.

