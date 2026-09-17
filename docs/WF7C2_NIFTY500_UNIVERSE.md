# WF7C2 — Reproducible Current NIFTY 500 Universe

WF7C2 needs a broader research universe, but the universe itself must be auditable.

This helper converts the **official NSE Indices NIFTY 500 constituent CSV** into the
same yfinance NSE ticker convention already consumed by ProVSA (`SYMBOL.NS`) and
records the SHA-256 of the exact downloaded CSV.

This remains research-only and does not alter scanner, qualification, scoring,
ranking, actionability, alerts, execution, or orders.

## Source

Official NSE Indices page:

- NIFTY 500: `https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-500`
- Constituent CSV:
  `https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv`

Do not replace the official CSV with a third-party symbol list.

## Important limitation

This is a **current-constituent** universe. It is not a historical point-in-time
membership series. Using it for historical WF7C2 analysis retains survivor-bias
and index-reconstitution limitations. The generated manifest records that warning
explicitly.

The helper intentionally does **not** assert that the file must contain exactly 500
rows. The branded index can temporarily contain a different number of securities
because of index-maintenance events; the official file is the authority for the run.

## Prepare the universe on Windows / PowerShell

```powershell
$universeDir = "reports\weekly-foundation\wf7c2-universe"
New-Item -ItemType Directory -Force -Path $universeDir | Out-Null

$source = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
$csv = Join-Path $universeDir "ind_nifty500list.csv"
Invoke-WebRequest -Uri $source -OutFile $csv

python -m audit.nse_index_universe `
  --csv $csv `
  --index-name "NIFTY 500" `
  --source-url $source `
  --output-dir $universeDir
```

The bundle contains:

- `wf7c2_nse_universe_manifest.json`
  - exact source SHA-256,
  - retrieval timestamp,
  - source symbols,
  - normalized provider symbols,
  - survivor-bias warning,
  - `is_actionable: false`.
- `wf7c2_symbols.txt`
  - one comma-separated `*.NS` string suitable for the existing WF7C2 CLI.

Keep the downloaded CSV and generated manifest with the eventual WF7C2 evidence
so the requested universe can be reconstructed exactly.

## Run WF7C2

```powershell
$symbols = Get-Content `
  "reports\weekly-foundation\wf7c2-universe\wf7c2_symbols.txt" `
  -Raw

python -m audit.weekly_broad_universe_robustness_runner `
  --symbols $symbols `
  --horizons 5,10,15 `
  --out-of-sample-start-week 2024-01-01 `
  --continue-on-symbol-error `
  --output-dir "reports\weekly-foundation\wf7c2-nifty500-2026-09-17"
```

Review the output before any production discussion:

1. requested versus successful symbols,
2. every provider/history failure,
3. exact input fingerprints,
4. evaluable treatment/control counts,
5. bullish and bearish legacy directions separately,
6. OOS matched edge and sign stability,
7. regime and era decomposition,
8. per-symbol concentration,
9. 5/10/15-week horizon stability.

If broad-universe evidence again shows sign reversals, weak effective samples, or
material symbol/regime/era dependence, WF7 should close with no production weekly
qualification change.
