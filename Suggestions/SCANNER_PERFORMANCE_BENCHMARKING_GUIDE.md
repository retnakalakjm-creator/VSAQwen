# VSAPro Scanner Performance Benchmarking & Results Template

**Date:** August 27, 2026  
**Purpose:** Track scanner optimization progress and validate improvements  
**Status:** Ready for implementation and testing

---

## 📊 BASELINE MEASUREMENT (Before Optimization)

### Setup
- **Environment:** Python 3.10+, pandas 2.0+, numpy 1.24+
- **Hardware:** Standard development machine (8GB RAM, multi-core CPU)
- **Dataset:** 200 weekly bars (~4 years of data)
- **Symbols Tested:** 8 NSE symbols (INFY.NS, SBIN.NS, HDFC.NS, etc.)

### Measurement Script (Baseline)

```python
import time
from data import download_data, daily_to_weekly
from metrics_engine import MetricsEngine
from scanner import ScannerEngine

def benchmark_baseline(symbol: str, iterations: int = 5) -> dict:
    """Measure current scanner performance."""
    times = {
        'download': [],
        'metrics': [],
        'scan': [],
        'total': []
    }
    
    for i in range(iterations):
        # Download
        start = time.perf_counter()
        daily = download_data(symbol, refresh=(i==0))  # Refresh only first time
        download_time = time.perf_counter() - start
        times['download'].append(download_time)
        
        # Metrics
        start = time.perf_counter()
        weekly = daily_to_weekly(daily)
        metrics = MetricsEngine().calculate(weekly)
        metrics_time = time.perf_counter() - start
        times['metrics'].append(metrics_time)
        
        # Scan
        start = time.perf_counter()
        candidates = ScannerEngine().scan_actionable(metrics)
        scan_time = time.perf_counter() - start
        times['scan'].append(scan_time)
        
        total = download_time + metrics_time + scan_time
        times['total'].append(total)
    
    # Calculate statistics
    return {
        'download': {
            'mean': sum(times['download']) / len(times['download']) * 1000,
            'min': min(times['download']) * 1000,
            'max': max(times['download']) * 1000,
        },
        'metrics': {
            'mean': sum(times['metrics']) / len(times['metrics']) * 1000,
            'min': min(times['metrics']) * 1000,
            'max': max(times['metrics']) * 1000,
        },
        'scan': {
            'mean': sum(times['scan']) / len(times['scan']) * 1000,
            'min': min(times['scan']) * 1000,
            'max': max(times['scan']) * 1000,
        },
        'total': {
            'mean': sum(times['total']) / len(times['total']) * 1000,
            'min': min(times['total']) * 1000,
            'max': max(times['total']) * 1000,
        }
    }

# Run benchmark
symbols = ["INFY.NS", "SBIN.NS", "HDFC.NS", "RELIANCE.NS", 
           "ICICIBANK.NS", "LT.NS", "TATASTEEL.NS", "BHARTIARTL.NS"]

print("BASELINE PERFORMANCE MEASUREMENTS")
print("=" * 80)

for symbol in symbols:
    results = benchmark_baseline(symbol)
    print(f"\n{symbol}")
    print(f"  Download: {results['download']['mean']:6.1f}ms (min {results['download']['min']:5.1f}, max {results['download']['max']:5.1f})")
    print(f"  Metrics:  {results['metrics']['mean']:6.1f}ms (min {results['metrics']['min']:5.1f}, max {results['metrics']['max']:5.1f})")
    print(f"  Scan:     {results['scan']['mean']:6.1f}ms (min {results['scan']['min']:5.1f}, max {results['scan']['max']:5.1f})")
    print(f"  Total:    {results['total']['mean']:6.1f}ms (min {results['total']['min']:5.1f}, max {results['total']['max']:5.1f})")
```

### EXPECTED BASELINE RESULTS

| Phase | Time | % of Total |
|-------|------|-----------|
| Download (cached) | 5ms | 5% |
| Metrics Engine | 10ms | 10% |
| **Scanner (scan_actionable)** | **110-190ms** | **80-85%** |
| **TOTAL** | **125-205ms** | **100%** |

### Breakdown of scan_actionable (110-190ms)

| Sub-phase | Time | % of Scan |
|-----------|------|----------|
| Data Copying (180 replays) | 15-25ms | 15-20% |
| Trend Analysis (180 TrendAnalyzer calls) | 50-100ms | 50-70% |
| Evidence Collection (180 EvidenceEngine calls) | 30-50ms | 25-35% |
| Qualification (history iteration) | 10-15ms | 10-15% |
| Professional Scoring | 5-10ms | 5-10% |

---

## ✅ OPTIMIZED PERFORMANCE (After Implementation)

### Phase 1: Critical Optimizations (Weeks 1)

**Optimizations Applied:**
1. Incremental Trend Analysis (-50% on trend analysis)
2. Remove Redundant Copies (-100% on data copying)

**Expected Results:**

| Phase | Baseline | Optimized | Improvement |
|-------|----------|-----------|------------|
| Data Copying | 15-25ms | 0ms | -100% |
| Trend Analysis | 50-100ms | 15-30ms | -70% |
| Evidence Collection | 30-50ms | 30-50ms | 0% |
| Qualification | 10-15ms | 10-15ms | 0% |
| Professional Scoring | 5-10ms | 5-10ms | 0% |
| **SCAN TOTAL** | **110-190ms** | **60-115ms** | **-40-50%** |

**Target:** Single symbol < 70ms ✓

### Measurement Script (Phase 1)

```python
from live_scanner_optimized import LiveScannerOptimized

def benchmark_optimized_phase1(symbol: str, iterations: int = 5) -> dict:
    """Measure optimized scanner (Phase 1)."""
    scanner = LiveScannerOptimized(track_performance=False)
    times = {'total': [], 'download': [], 'metrics': []}
    
    for i in range(iterations):
        # Download & metrics (same as baseline)
        start = time.perf_counter()
        daily = download_data(symbol, refresh=(i==0))
        weekly = daily_to_weekly(daily)
        metrics = MetricsEngine().calculate(weekly)
        download_and_metrics = time.perf_counter() - start
        
        # Optimized scan
        start = time.perf_counter()
        candidate = scanner._scan_latest_optimized(metrics)
        scan_time = time.perf_counter() - start
        
        times['download'].append(download_and_metrics)
        times['total'].append(download_and_metrics + scan_time)
    
    return {
        'download_metrics': sum(times['download']) / len(times['download']) * 1000,
        'scan': (sum(times['total']) / len(times['total']) * 1000 - 
                 sum(times['download']) / len(times['download']) * 1000),
        'total': sum(times['total']) / len(times['total']) * 1000
    }
```

### Phase 2: Important Optimizations (Weeks 2)

**Optimizations Applied:**
1. Evidence Delta Tracking (-30% on evidence collection)
2. Qualification Caching (-50% on qualification)

**Expected Results:**

| Phase | Phase 1 | Phase 2 | Improvement |
|-------|---------|---------|------------|
| Data Copying | 0ms | 0ms | - |
| Trend Analysis | 15-30ms | 15-30ms | 0% |
| Evidence Collection | 30-50ms | 18-30ms | -40% |
| Qualification | 10-15ms | 5-10ms | -50% |
| Professional Scoring | 5-10ms | 5-10ms | 0% |
| **SCAN TOTAL** | **60-115ms** | **43-80ms** | **-28%** |

**Target:** Single symbol < 45ms ✓

### Phase 3: Nice-to-Have (Weeks 3+)

**Optimizations Applied:**
1. Parallel Symbol Scanning (3-4x for 8 symbols)
2. Compiled Classifiers (+5-10% on metrics)

**Expected Results:**

| Scenario | Baseline | Optimized | Improvement |
|----------|----------|-----------|------------|
| 1 symbol (sequential) | 125-205ms | 35-50ms | **72-83%** |
| 8 symbols (sequential) | 1000-1640ms | 280-400ms | **72-83%** |
| 8 symbols (parallel, 4 workers) | 1000-1640ms | 120-150ms | **85-90%** |

**Target:** 8 symbols in parallel < 150ms ✓

---

## 🎯 RESULTS MEASUREMENT TEMPLATE

### Template for Each Optimization Phase

```
================================================================================
OPTIMIZATION PHASE: [Name]
Date: [Date]
Implementation: [Description of changes]
================================================================================

SINGLE SYMBOL PERFORMANCE
├─ Symbol: INFY.NS
│  ├─ Baseline:     125ms
│  ├─ Optimized:    45ms
│  ├─ Improvement:  64% faster
│  └─ Confidence:   [high/medium/low]
│
├─ Symbol: SBIN.NS
│  └─ [same format]
│
└─ Average: [calculate mean improvement]

MULTI-SYMBOL PERFORMANCE (8 symbols)
├─ Sequential (original):  1240ms (155ms/symbol)
├─ Sequential (optimized): 380ms (47.5ms/symbol)
├─ Improvement:            69% faster
│
├─ Parallel (4 workers):   115ms (14.4ms/symbol)
├─ vs Sequential:          3.3x faster
└─ Parallel Speedup:       [calculation]

MEMORY USAGE
├─ Baseline:  [measure peak memory]
├─ Optimized: [measure peak memory]
├─ Reduction: [calculate percentage]
└─ Data Copies Eliminated: [count]

CODE QUALITY CHECKS
├─ All unit tests pass:     [yes/no]
├─ Integration tests pass:  [yes/no]
├─ Accuracy vs baseline:    [same/improved/degraded]
├─ Edge cases handled:      [yes/no]
└─ Documentation updated:   [yes/no]

ISSUES ENCOUNTERED
├─ Issue 1: [description]
│  └─ Resolution: [how it was fixed]
├─ Issue 2: [...]
└─ Lessons Learned: [key takeaways]

ROLLOUT READINESS
├─ Performance target met:  [yes/no]
├─ Risk level:             [low/medium/high]
├─ Recommended action:     [deploy/revise/defer]
└─ Next phase approved:    [yes/no]
================================================================================
```

### Example Completed Template (Phase 1)

```
================================================================================
OPTIMIZATION PHASE: Critical Bottlenecks (Phase 1)
Date: September 2, 2026
Implementation: 
  1. Incremental Trend Analysis (TrendAnalyzer.analyze_incremental)
  2. Removed deep DataFrame copies (using iloc views)
  3. Optimized week_at() string conversion
================================================================================

SINGLE SYMBOL PERFORMANCE
├─ Symbol: INFY.NS
│  ├─ Baseline:     145ms
│  ├─ Optimized:    52ms
│  ├─ Improvement:  64% faster
│  └─ Confidence:   high
│
├─ Symbol: SBIN.NS
│  ├─ Baseline:     138ms
│  ├─ Optimized:    48ms
│  ├─ Improvement:  65% faster
│  └─ Confidence:   high
│
├─ Symbol: HDFC.NS
│  └─ Baseline: 152ms → Optimized: 54ms (64% faster)
│
├─ Symbol: RELIANCE.NS
│  └─ Baseline: 141ms → Optimized: 49ms (65% faster)
│
└─ Average: 144ms → 51ms (65% faster) ✓ TARGET MET

MULTI-SYMBOL PERFORMANCE (8 symbols)
├─ Sequential (original):  1150ms (144ms/symbol)
├─ Sequential (optimized): 410ms (51ms/symbol)
├─ Improvement:            64% faster ✓
│
└─ Parallel (4 workers):   125ms (15.6ms/symbol)
   vs Sequential:          3.3x faster
   Parallel Speedup:       9.2x vs baseline sequential

MEMORY USAGE
├─ Baseline:  185MB (180 DataFrame copies in memory)
├─ Optimized: 42MB (using views, no copies)
├─ Reduction: 77% less memory ✓
└─ Data Copies Eliminated: 180 → 0

CODE QUALITY CHECKS
├─ All unit tests pass:     YES ✓
├─ Integration tests pass:  YES ✓
├─ Accuracy vs baseline:    IDENTICAL (validated on 500+ candidates)
├─ Edge cases handled:      YES (empty data, single bar, etc.)
└─ Documentation updated:   YES (VSAPro_LIVE_SCANNER_PERFORMANCE_ANALYSIS.md)

ISSUES ENCOUNTERED
├─ Issue 1: IncrementalTrendAnalyzer false negatives on first bar
│  └─ Resolution: Added full analysis on first call
├─ Issue 2: DataFrame views caused warnings in some engines
│  └─ Resolution: Verified all engines compatible with views (no copy-on-write)
└─ Lessons Learned: 
    - Trend analysis is legitimately O(n²) without caching
    - DataFrame views are safe and should be used consistently

ROLLOUT READINESS
├─ Performance target met:  YES (64% improvement, target was 60%) ✓
├─ Risk level:             LOW (only optimization, no semantic changes)
├─ Recommended action:     DEPLOY IMMEDIATELY
└─ Next phase approved:    YES (Phase 2 can begin)

OBSERVED BENEFITS
├─ Production readiness:    Can now support real-time scanning
├─ Cost reduction:          85% less memory pressure
├─ Scaling:                 8 symbols in 125ms (vs 1150ms baseline)
└─ User experience:         Instant results for live trading

MEASUREMENTS METHODOLOGY
├─ Warmup runs:            3 (not included in stats)
├─ Measurement runs:       20 per symbol
├─ Outlier handling:       Trimmed 5% highest/lowest
├─ Time source:            time.perf_counter()
└─ Confidence:             95% (repeated measurements, low variance)
================================================================================
```

---

## 📈 PERFORMANCE TRACKING OVER TIME

### Create Tracking Sheet

**Spreadsheet:** `scanner_performance_tracking.csv`

```csv
Date,Phase,Symbol,Baseline_ms,Optimized_ms,Improvement_Pct,Target_ms,Status
2026-08-27,Baseline,INFY.NS,145,145,0,70,baseline
2026-09-02,Phase1,INFY.NS,145,52,64.1,70,✓ met
2026-09-02,Phase1,SBIN.NS,138,48,65.2,70,✓ met
2026-09-02,Phase1,Average,144,51,64.6,70,✓ met
2026-09-09,Phase2,INFY.NS,52,38,26.9,45,⚠ not met yet
2026-09-09,Phase2,SBIN.NS,48,35,27.1,45,⚠ not met yet
2026-09-09,Phase2,Average,51,37,27.5,45,⚠ continue opt
```

### Dashboard Template

```python
import pandas as pd
import matplotlib.pyplot as plt

def plot_performance_progress(csv_file):
    """Plot optimization progress over time."""
    df = pd.read_csv(csv_file)
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # Plot 1: Absolute time improvement
    phases = df.groupby('Phase')['Optimized_ms'].mean()
    axes[0, 0].bar(phases.index, phases.values, color='green', alpha=0.7)
    axes[0, 0].axhline(y=50, color='r', linestyle='--', label='Target: 50ms')
    axes[0, 0].set_title('Optimized Time by Phase')
    axes[0, 0].set_ylabel('Time (ms)')
    
    # Plot 2: Percentage improvement
    improvements = df.groupby('Phase')['Improvement_Pct'].mean()
    axes[0, 1].plot(improvements.index, improvements.values, marker='o', linewidth=2)
    axes[0, 1].set_title('Cumulative Improvement')
    axes[0, 1].set_ylabel('Improvement (%)')
    axes[0, 1].grid(True, alpha=0.3)
    
    # Plot 3: Symbols comparison
    latest = df[df['Phase'] == df['Phase'].max()]
    symbols = latest['Symbol'].unique()
    x = range(len(symbols))
    axes[1, 0].bar([i - 0.2 for i in x], latest['Baseline_ms'], width=0.4, label='Baseline', alpha=0.7)
    axes[1, 0].bar([i + 0.2 for i in x], latest['Optimized_ms'], width=0.4, label='Optimized', alpha=0.7)
    axes[1, 0].set_xticks(x)
    axes[1, 0].set_xticklabels(symbols, rotation=45)
    axes[1, 0].set_title('Performance by Symbol')
    axes[1, 0].set_ylabel('Time (ms)')
    axes[1, 0].legend()
    
    # Plot 4: Status summary
    status_counts = df['Status'].value_counts()
    axes[1, 1].pie(status_counts.values, labels=status_counts.index, autopct='%1.1f%%')
    axes[1, 1].set_title('Optimization Status')
    
    plt.tight_layout()
    plt.savefig('scanner_performance_progress.png', dpi=300)
    print("Chart saved: scanner_performance_progress.png")

# Usage
plot_performance_progress('scanner_performance_tracking.csv')
```

---

## 🔄 CONTINUOUS MONITORING

### Production Metrics Collection

```python
class ProductionMetricsCollector:
    """Collect real production scanner metrics."""
    
    def __init__(self, log_file: str = "scanner_production_metrics.log"):
        self.log_file = log_file
    
    def log_scan(self, symbol: str, duration_ms: float, actionable: bool, 
                 confidence: float, candidate_type: str = "unknown"):
        """Log a single scan execution."""
        from datetime import datetime
        
        timestamp = datetime.now().isoformat()
        entry = (
            f"{timestamp}|{symbol}|{duration_ms:.1f}ms|"
            f"actionable={actionable}|confidence={confidence:.3f}|type={candidate_type}\n"
        )
        
        with open(self.log_file, 'a') as f:
            f.write(entry)
    
    def analyze_production_metrics(self, lookback_hours: int = 24):
        """Analyze recent production performance."""
        from datetime import datetime, timedelta
        
        cutoff = datetime.now() - timedelta(hours=lookback_hours)
        scans = []
        
        with open(self.log_file, 'r') as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 3:
                    timestamp = datetime.fromisoformat(parts[0])
                    if timestamp > cutoff:
                        symbol = parts[1]
                        duration = float(parts[2].rstrip('ms'))
                        scans.append({'symbol': symbol, 'duration': duration})
        
        if not scans:
            print(f"No production metrics in past {lookback_hours} hours")
            return
        
        durations = [s['duration'] for s in scans]
        
        print(f"\nProduction Metrics ({lookback_hours}h lookback)")
        print(f"  Total scans:        {len(scans)}")
        print(f"  Average time:       {sum(durations)/len(durations):.1f}ms")
        print(f"  Min time:           {min(durations):.1f}ms")
        print(f"  Max time:           {max(durations):.1f}ms")
        print(f"  P95 time:           {sorted(durations)[int(len(durations)*0.95)]:.1f}ms")
        print(f"  P99 time:           {sorted(durations)[int(len(durations)*0.99)]:.1f}ms")

# Usage in production
collector = ProductionMetricsCollector()

# In scan_live():
start = time.perf_counter()
candidate = scan_live(symbol)
duration = (time.perf_counter() - start) * 1000

collector.log_scan(
    symbol=symbol,
    duration_ms=duration,
    actionable=candidate.actionable if candidate else False,
    confidence=candidate.confidence if candidate else 0.0
)

# Analysis
collector.analyze_production_metrics(lookback_hours=24)
```

---

## ✅ SUCCESS CRITERIA CHECKLIST

### Phase 1: Critical Optimizations

- [ ] Incremental TrendAnalyzer implemented and tested
- [ ] DataFrame copy removed from scan_to_index()
- [ ] All tests passing (unit + integration)
- [ ] Single symbol performance: 50-70ms (target: < 70ms)
- [ ] 8-symbol performance: 400-560ms sequential
- [ ] Memory usage reduced by 70%+
- [ ] Documentation updated
- [ ] Code review approved
- [ ] Deploy to staging

### Phase 2: Important Optimizations

- [ ] DeltaEvidenceEngine implemented
- [ ] Qualification caching implemented
- [ ] Single symbol performance: 35-50ms (target: < 45ms)
- [ ] Cache hit rate: > 80%
- [ ] All tests passing
- [ ] Rollback plan prepared
- [ ] Deploy to production

### Phase 3: Infrastructure

- [ ] Parallel symbol scanning working
- [ ] 8-symbol parallel performance: 120-150ms (target: < 150ms)
- [ ] ThreadPoolExecutor usage documented
- [ ] Error handling for failed scans
- [ ] Monitoring and alerting in place

---

## 📝 SUMMARY

This benchmarking guide provides:
1. **Baseline measurements** - Establish current performance
2. **Optimization verification** - Measure improvements after each phase
3. **Production monitoring** - Track real-world performance
4. **Success criteria** - Clear targets and acceptance tests

**Next Steps:**
1. Run baseline benchmark on your hardware
2. Document baseline results
3. Implement Phase 1 optimizations
4. Re-run benchmarks to verify improvement
5. Proceed to Phase 2 if targets met

---

**Document Version:** 1.0  
**Last Updated:** August 27, 2026  
**Status:** Ready for implementation and testing
