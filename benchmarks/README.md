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
