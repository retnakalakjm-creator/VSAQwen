# INCREASING_DEMAND Audit

## Final Provisional State

- **Status:** PROVISIONAL
- **Base weight:** 0.85
- **Conflict penalty:** 0.10
- **Effective conflict weight:** 0.765
- **Clean-event weight:** 0.85
- **Rejection rule:** NO
- **Production:** NOT REGISTERED / provisional

## Detector Definition

Validated production definition uses four mandatory conditions:

1. Bullish bar
2. High volume
3. Above-average spread
4. Increasing volume

The detector is connected to `collect_demand()` and emits through the helper-level weight path.

## Production Path Audit

Historical production replay established:

- 905 production hits across 8 symbols
- All observed target weights: **0.85**
- Registry profile: weight **0.85**, strength **0.90**

The production-path audit was optimized after the original prefix-replay implementation proved excessively slow. Future audits should avoid rebuilding the full `EvidenceEngine` for every historical bar.

## Interaction / Contradiction Audit

The optimized same-bar contradiction audit produced:

- 902 detector-aligned events
- 41 events with supply-side conflict
- Conflict rate: **4.55%**
- `HIDDEN_SUPPLY_LIKE`: 41
- `BUYING_CLIMAX_LIKE`: 16
- `UPTHRUST_LIKE`: 1
- `SUPPLY_COMING_IN_LIKE`: 0
- `INCREASING_SUPPLY_LIKE`: 0
- `NO_DEMAND_LIKE`: 0

Conclusion: direct supply contradictions are uncommon. No rejection rule is justified.

## Conflict Outcome Audit

Using the project's 8-bar forward-return methodology:

- Usable demand events: **899**
- Conflict events: **41**
- Clean events: **858**
- Conflict rate: **4.56%**
- Conflict mean return: **+0.72%**
- Clean mean return: **+3.83%**
- Mean-return gap: **-3.11 percentage points**
- Conflict positive rate: **51.22%**
- Clean positive rate: **59.44%**
- Positive-rate gap: **-8.22 percentage points**

The conflict subset is weaker on average, despite remaining positive in aggregate. Results vary by symbol, so conflict events should not be rejected outright.

## Penalty Sensitivity Audit

Tested penalties:

`0.00, 0.05, 0.10, 0.15, 0.20`

Recommended provisional penalty: **0.10**.

Corresponding effective weights:

| Conflict penalty | Effective conflict weight | Clean weight |
|---:|---:|---:|
| 0.00 | 0.850 | 0.850 |
| 0.05 | 0.8075 | 0.850 |
| 0.10 | 0.765 | 0.850 |
| 0.15 | 0.7225 | 0.850 |
| 0.20 | 0.680 | 0.850 |

## Decision

Freeze `INCREASING_DEMAND` at:

**Base weight 0.85 + conflict penalty 0.10 + no rejection rule.**

This remains a provisional calibration result. Do not promote to production registration until the broader production qualification process is completed.

## Audit Principles Preserved

- Real-market evidence may be imperfect; textbook purity is not required.
- Interaction conflicts reduce evidence quality only when empirical outcome evidence supports doing so.
- Detector semantics remain unchanged by the penalty.
- Weight tuning does not alter event detection.
