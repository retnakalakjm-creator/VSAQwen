# Standard VSA Audit Basket

This is a Milestone 6 audit/calibration support document.

PR #77 defines one repeatable 30-symbol basket so detector calibration is not judged from one or two examples only.

## Why this exists

The LT.NS March 2026 case showed strong Effort-vs-Result, absorption, high-volume reversal, and qualification-lifecycle review candidates. The first small basket also showed similar candidates in RELIANCE.NS and SRF.NS.

Before changing production detector rules, we need to run the same audit workflow over the same basket every time. That gives us a stable false-positive review baseline.

## Scope guard

This basket is audit-only.

It does not:

- Download market data by itself.
- Call a provider by itself.
- Replay the scanner by itself.
- Persist scanner state.
- Change production detector rules.
- Change scanner scoring or ranking.
- Change API behavior.
- Change frontend behavior.
- Add broker, order, account, funds, holdings, margin, credential, or position-sizing behavior.

## Basket

The standard basket is named:

```text
milestone6_standard_india_large_cap_30
```

Symbols:

```text
LT.NS,RELIANCE.NS,SRF.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS,AXISBANK.NS,SBIN.NS,KOTAKBANK.NS,BAJFINANCE.NS,HINDUNILVR.NS,ITC.NS,BHARTIARTL.NS,ASIANPAINT.NS,MARUTI.NS,M&M.NS,TATAMOTORS.NS,TATASTEEL.NS,JSWSTEEL.NS,SUNPHARMA.NS,CIPLA.NS,DRREDDY.NS,ULTRACEMCO.NS,GRASIM.NS,ONGC.NS,NTPC.NS,POWERGRID.NS,ADANIPORTS.NS,COALINDIA.NS
```

Default audit window:

```text
start_week=2026-03-02
horizon_weeks=8
max_symbols=30
```

The start week intentionally matches the LT.NS March 2026 case so the same high-volume reversal period can be compared across the basket.

## Command helper

Print the basket and commands:

```powershell
python scripts/vsa_standard_audit_basket.py
```

Print JSON:

```powershell
python scripts/vsa_standard_audit_basket.py --json
```

Override window only for ad hoc review:

```powershell
python scripts/vsa_standard_audit_basket.py --start-week 2025-02-24 --horizon-weeks 20
```

## Full workflow

Start backend separately:

```powershell
uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

Generate the raw audit JSON:

```powershell
curl.exe "http://127.0.0.1:8000/api/vsa-audit/events?symbols=LT.NS,RELIANCE.NS,SRF.NS,TCS.NS,INFY.NS,HDFCBANK.NS,ICICIBANK.NS,AXISBANK.NS,SBIN.NS,KOTAKBANK.NS,BAJFINANCE.NS,HINDUNILVR.NS,ITC.NS,BHARTIARTL.NS,ASIANPAINT.NS,MARUTI.NS,M&M.NS,TATAMOTORS.NS,TATASTEEL.NS,JSWSTEEL.NS,SUNPHARMA.NS,CIPLA.NS,DRREDDY.NS,ULTRACEMCO.NS,GRASIM.NS,ONGC.NS,NTPC.NS,POWERGRID.NS,ADANIPORTS.NS,COALINDIA.NS&start_week=2026-03-02&horizon_weeks=8&max_symbols=30" -o standard_basket_audit.json
```

Generate high-priority candidate events:

```powershell
python scripts/vsa_audit_candidate_events.py standard_basket_audit.json --min-priority high --output standard_basket_candidate_events_high.json
```

Generate basket review JSON and CSV:

```powershell
python scripts/vsa_audit_batch_review.py standard_basket_candidate_events_high.json --min-priority high --json-output standard_basket_review.json --csv-output standard_basket_review.csv
```

## How to use the output

Review in this order:

1. `standard_basket_review.json` summary counts.
2. `top_review_symbols` for the worst symbols.
3. `review_focus` for dominant candidate families.
4. `standard_basket_review.csv` sorted by symbol, week, and candidate family.
5. Manual chart inspection only for high-priority rows.

The goal is to decide whether candidate families are clean enough to move toward production evidence, or noisy enough to remain audit-only.
