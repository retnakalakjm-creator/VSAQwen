# Scanner performance benchmarks

This folder contains opt-in benchmark tooling for measuring current production scanner performance before changing incremental trend/evidence internals.

The benchmark is intentionally not part of pytest because realistic 100/500-symbol runs depend on network, cache state, disk speed, and local machine resources.

## What is measured

`benchmark_scanner_performance.py` records:

- wall-clock time
- peak Python allocation memory from `tracemalloc`
- daily bars processed
- weekly/metrics bars processed
- total bars processed
- bars processed per second
- candidate count
- actionable candidate count

`tracemalloc` measures Python allocations. It does not capture every native allocation made by pandas, NumPy, pyarrow, or the OS.

## Scenarios

Default scenarios are:

- `cold_1_symbol`: removes local cache files for the first symbol, then scans it.
- `warm_1_symbol`: scans the first symbol using the existing local cache when available.
- `scan_100_symbols`: scans the first 100 symbols from the supplied universe.
- `scan_500_symbols`: scans the first 500 symbols from the supplied universe.

Warm and multi-symbol scenarios use a very large cache age to avoid unnecessary recent refreshes when cache files already exist. Missing symbols will still be downloaded and cached.

By default, scanner state is isolated per scenario so the benchmark focuses on the current production scan path without accidentally reusing previous local state. Use `--reuse-state` when you specifically want to measure persisted incremental resume behavior between scenarios.

## Symbol universe file

Create a text file with one ticker per line:

```text
SRF.NS
RELIANCE.NS
TCS.NS
INFY.NS
```

For realistic 100/500-symbol results, use at least 500 unique symbols. `--allow-repeat` is available only to smoke-test the benchmark harness; repeated symbols do not represent real production throughput.

## Commands

One-symbol cache baseline:

```cmd
python benchmarks\benchmark_scanner_performance.py --scenarios cold_1_symbol warm_1_symbol
```

Full realistic baseline:

```cmd
python benchmarks\benchmark_scanner_performance.py --symbols-file symbols.txt
```

Smoke-test all scenarios with one symbol repeated:

```cmd
python benchmarks\benchmark_scanner_performance.py --allow-repeat
```

Measure persisted incremental resume behavior:

```cmd
python benchmarks\benchmark_scanner_performance.py --symbols-file symbols.txt --reuse-state
```

Results are written to `benchmarks/results/` as JSON and CSV.


## Deterministic transition replay benchmark

`benchmark_transition_replay.py` is the offline G2 benchmark for the optimized
causal transition path. It does not download data and does not depend on cache
state.

It generates deterministic synthetic weekly OHLCV, asserts legacy-vs-transition
candidate parity, then measures:

- legacy full historical replay through `ScannerEngine`
- optimized full historical replay through `HistoricalScannerRunner`
- one-new-bar update from in-memory `ScanState`
- one-new-bar resume from durable `ScannerState`

No timing threshold is enforced in pytest because absolute performance depends on
the machine and Python build. The active regression tests protect semantic parity
and benchmark result shape; the benchmark itself reports measured timings.

Run the default benchmark:

```cmd
python benchmarks\benchmark_transition_replay.py
```

Run a longer local benchmark:

```cmd
python benchmarks\benchmark_transition_replay.py --bars 192 --repeats 7 --warmups 2
```

Results are printed to the terminal and written as JSON under
`benchmarks/results/`.


### G2 measured result — 2026-09-18

Local run:

```cmd
python benchmarks\benchmark_transition_replay.py --bars 192 --repeats 7 --warmups 2
```

Measured medians on the validation machine:

| Scenario | Median |
|---|---:|
| Legacy full replay | 1386.595 ms |
| Optimized transition full replay | 1330.784 ms |
| In-memory one-new-bar update | 6.228 ms |
| Durable one-new-bar resume | 7.672 ms |

Observed ratios:

- full replay: **1.042x** faster (about **4.0%** lower median wall time)
- in-memory one-new-bar update vs legacy full replay: **222.653x** faster
- durable one-new-bar resume vs legacy full replay: about **180.7x** faster

Interpretation: G1 materially improves the intended rolling/new-bar production path.
It does **not** materially transform full historical replay throughput; additional
full-replay optimization should be treated as a separate evidence-driven task,
not inferred from the strong incremental result.

Retained result:
`benchmarks/results/transition_replay_20260918-135316.json`.
