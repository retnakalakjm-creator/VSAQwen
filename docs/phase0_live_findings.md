# Phase 0 Live Integration Findings Log

Use this file to record real-market-data validation results from `docs/local_smoke_test.md`.

Do not add feature work until blocking findings are fixed or explicitly accepted as non-blocking.

## Run metadata

```text
Date/time:
Machine/OS:
Python version:
Node version:
Provider: yfinance/upstox
Symbols checked:
Backend command:
Frontend command:
```

## Scanner path verification

```text
Confirmed API analysis uses scan_latest_candidate_production: yes/no
Direct ScannerEngine().scan_to_index in confirmed API path: yes/no
Developing preview uses direct scan_to_index only for preview: yes/no
Scanner state created/refreshed after confirmed analysis: yes/no
Second confirmed analysis succeeds from production path: yes/no
Notes:
```

## Real-market-data checks

| Symbol | Provider | Confirmed context | Full analysis | Developing preview | Journal | Data source | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| SRF.NS | yfinance | pending | pending | pending | pending | pending | |
| RELIANCE.NS | yfinance | pending | pending | pending | pending | pending | |
| TCS.NS | yfinance | pending | pending | pending | pending | pending | |

## Optional Upstox checks

| Symbol | Enabled | Token present only | Mapped | Optional fetch | Token hidden | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| RELIANCE.NS | pending | pending | pending | optional | pending | |
| TCS.NS | pending | pending | pending | optional | pending | |

## Findings

### Finding 1

```text
Status: open/fixed/non-blocking
Symbol:
Endpoint or UI panel:
Expected:
Actual:
Error/log:
Decision impact:
Fix PR:
```

## Phase 0 sign-off

Phase 0 is ready to close only when:

```text
all required yfinance symbols were checked with real market data
confirmed API scanner path was verified
frontend confirmed/developing/journal/data-source panels worked together
no forbidden broker/order/account scope was observed
blocking findings are fixed or tracked in focused PRs
```
