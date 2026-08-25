# VSA Event Audit Status Index

This is the **pre-decision index** for VSA events already worked on in the project.

Before changing an event's detector semantics, scoring weight, qualification, actionability, rejection logic, or interaction policy, check this file first.

## Decision rule

An event marked **Audit-complete / Frozen** must not be re-audited merely because it is encountered again in the production event sequence.

Re-run an audit only when one of these changes:

- production detector logic or event semantics;
- professional scoring architecture or scoring-map treatment;
- qualification/actionability logic;
- the point-in-time candidate population contract;
- a material production-path integration change.

Runtime `Evidence.weight` is **emission metadata** and must not be confused with the professional scoring maps such as `SUPPLY_EVIDENCE_WEIGHTS` or `DEMAND_EVIDENCE_WEIGHTS`.

## Audited event index

| Event | Production Status | Base Weight | Empirical Provenance | Win Rate | Mean 8-Bar Return |
|---|---|---:|---|---:|---:|
| **STOPPING_VOLUME** | ✅ Production-Active / validation-complete | `1.00` | Primary demand anchor; 59-event point-in-time validation across 8 symbols. | **73.58%** | Not frozen in the available audit summary |
| **SHAKEOUT** | ✅ Production-Active / validation-complete | `0.50` | Primary reversal/demand event; recovery-anchored production semantics. | Not frozen in the available audit summary | Not frozen in the available audit summary |
| **TEST** | ✅ Production-Active / non-scoring | `0.00` | Contextual confirmation only; non-scoring. 47 validated events were audited. | Not frozen as standalone decision-value metric | Not frozen as standalone decision-value metric |
| **NO_SUPPLY** | ✅ Production-Active / contextual-non-scoring | `0.00` / no scoring-map entry | Contextual demand-absence evidence; semantic and production-readiness audits complete. | **60.87%** | **+1.02%** |
| **NO_DEMAND** | ✅ Production-Active / audit-complete | `0.60` professional supply-map | Demand-absence / weakness; 109 production emissions from 202 cheap candidates. | **63.30%** | **+3.62%** |
| **BUYING_CLIMAX** | ✅ Production-Active / audit-complete | `1.00` registry / dynamic runtime | Primary supply weakness / climax; 181 production emissions; empirical `0.38` is calibration-only. | Not frozen as a standalone exact-event metric in the final audit record | Not frozen as a standalone exact-event metric in the final audit record |
| **SUPPLY_COMING_IN** | ✅ Production-Active / audit-complete | `1.00` registry / dynamic runtime | Primary supply weakness; 189/189 production emissions; empirical `0.38` calibration-only; `INCREASING_SUPPLY` overlap was confirming. | **62.96%** | **+3.76%** |
| **INCREASING_SUPPLY** | ✅ Active / audit-complete | `0.85` registry / `0.70` configured map / runtime `1.00` | Primary supply weakness; 528 emissions from 1,022 cheap candidates. | **63.45%** | **+3.06%** |
| **HIDDEN_SUPPLY** | ✅ Active / audit-complete / non-scoring | Existing | Supporting supply; 139 audited events; not promoted as incremental scoring evidence. | **58.99%** | **+2.78%** |
| **UPTHRUST** | ✅ Production-Active / audit-complete | `1.00` registry / `0.90` professional supply-map / dynamic runtime | Supply/distribution trap; 1,319 cheap candidates → 289 production emissions. Pure `INCREASING_DEMAND` interaction was weaker. Counterfactual penalty was rejected because it moved `net_strength` in the wrong direction. | **59.03%** | **+2.81%** |
| **SUPPLY_DRYING_UP** | ✅ Production-Active / audit-complete | `1.00` registry / `0.60` professional supply-map / runtime `1.00` | Contextual supply exhaustion; 547 cheap candidates → 225 production emissions. Modest hit-rate selectivity but slightly negative mean-return lift vs market. | **61.78%** | **+3.56%** |
| **INCREASING_DEMAND** | ⚠️ Production-Connected / provisional | `0.85` scoring-map / runtime `0.85` | Robust calibration: 902 events across 8 symbols; 26 beneficial vs 15 harmful decision changes; net benefit +11; leave-one-symbol-out minimum net benefit +6. Conflict subgroup: 41/902 (4.55%) with −8.22 pp hit-rate gap and −3.11 pp mean-return gap vs clean. Audited `0.10` conflict penalty remains study-only and is NOT active in production. | **59.44% clean** | **+3.83% clean** |
| **DEMAND_COMING_IN** | ⚠️ Production-Connected / provisional | `0.38` audit/integration weight | Positive aggregate decision value (+5.52 pp hit-rate lift; +0.35 pp mean-return lift) but mixed temporal stability and a small/conflicted bias-changing subgroup. No production conflict penalty; no promotion. | **66.19%** | **+4.13%** |

## Frozen event decisions

### STOPPING_VOLUME

- Production-active and validation-complete.
- No new production decision is pending from the audits already completed.
- Do not rerun unless production semantics or scoring architecture changes.

### SHAKEOUT

- Production-active / validation-complete.
- Existing contextual interaction policy remains part of the frozen state.
- Do not rerun unless production semantics or scoring architecture changes.

### TEST

- Production-active but explicitly **non-scoring/contextual**.
- Do not turn contextual evidence into a scoring weight merely because it overlaps another event.

### NO_SUPPLY

- Remains contextual/non-scoring.
- Standalone decision value is near market on hit rate but materially weaker on return magnitude.
- No scoring-map entry; weight sensitivity is not applicable.
- No production penalty or rejection rule.

### NO_DEMAND

- Production-active / audit-complete.
- Positive-rate lift exists, while mean-return lift is slightly negative.
- Weight sensitivity changed score/ranking but not qualification/actionability.
- No production penalty or rejection change.

### BUYING_CLIMAX

- Production-active / audit-complete.
- Registry weight is `1.00`; runtime scoring weight is dynamic.
- Empirical reference `0.38` is **not** the production runtime weight.
- The old provisional `INCREASING_DEMAND + UPTHRUST` penalty is rejected and must not be treated as production logic.

### SUPPLY_COMING_IN

- Production-active / audit-complete.
- `INCREASING_SUPPLY` overlap is confirming rather than a contradiction requiring a penalty.
- No production interaction penalty.

### INCREASING_SUPPLY

- Active / audit-complete.
- Shows positive-rate lift but lower mean return than market.
- Weight sensitivity has real score/ranking impact but no qualification/actionability change.
- No interaction penalty justified.

### HIDDEN_SUPPLY

- Active / audit-complete / non-scoring.
- Standalone decision value is negative versus eligible market.
- Retain as supporting contextual evidence; do not promote automatically.

### UPTHRUST

- Production-active / audit-complete.
- Decision value is negative versus eligible market.
- `INCREASING_DEMAND` overlap is empirically weaker but remains diagnostic/study-only.
- No production interaction penalty, no global weight change, no rejection rule.

### SUPPLY_DRYING_UP

- Production-active / audit-complete.
- Production role: `contextual_supply_exhaustion`.
- Decision value: `+0.99 pp` positive-rate lift vs market, but `-0.26 pp` mean-return lift.
- `TEST` improves hit rate but reduces mean-return magnitude.
- `NO_SUPPLY` slightly improves hit rate but materially reduces follow-through magnitude.
- `NO_SUPPLY + TEST` is too small for calibration.
- No production interaction bonus, penalty, rejection rule, or global weight promotion.

### INCREASING_DEMAND

- Production-connected but **provisional**.
- Keep the current `0.85` base scoring weight provisional.
- Calibration evidence is robust: 26 beneficial vs 15 harmful decision changes; net benefit `+11`; leave-one-symbol-out minimum net benefit `+6`.
- Conflict degradation is materially real: conflict rate `4.55%`, positive-rate gap `-8.22 pp`, mean-return gap `-3.11 pp` versus clean events.
- Keep the audited `0.10` conflict penalty **study-only / NOT ACTIVE**.
- No rejection rule, qualification change, actionability change, or emission-semantic change.
- Do not rerun the existing audits unless production semantics, scoring architecture, population contract, a new independent validation window, or the counterfactual framework materially changes.

### DEMAND_COMING_IN

- Production-connected but **provisional** at `0.38`.
- Positive overall decision value: `+5.52 pp` positive-rate lift and `+0.35 pp` mean-return lift versus eligible market.
- Temporal stability is mixed: 3 of 4 chronological windows were positive; the first was `-7.97 pp`.
- Only 12 / 281 events changed final bias; the changed-decision subgroup had better mean magnitude but worse positive hit rate.
- Keep conflict penalty at `0.00`.
- No production promotion, rejection rule, qualification change, actionability change, or semantic change.
- Do not rerun the existing audits from the same sample.

## Audits completed so far

```text
STOPPING_VOLUME       candidate / validation
SHAKEOUT              validation
TEST                  validation / contextual role
NO_SUPPLY             candidate / semantic / interaction / decision-value / readiness
NO_DEMAND             candidate / semantic / interaction / decision-value / weight sensitivity / readiness
BUYING_CLIMAX         candidate / semantic / production path / interaction study
SUPPLY_COMING_IN      candidate / production path / decision value / interaction
INCREASING_SUPPLY     candidate / semantic / interaction / decision value / weight sensitivity / readiness
HIDDEN_SUPPLY         candidate / semantic / interaction / decision value
UPTHRUST              candidate / semantic / interaction / exact combinations / decision value / readiness / counterfactual
SUPPLY_DRYING_UP      candidate / semantic / interaction / exact combinations / decision value / readiness
INCREASING_DEMAND     candidate / semantic / interaction / conflict / calibration / leave-one-symbol-out / decision synthesis
DEMAND_COMING_IN      candidate / semantic / interaction / decision-value / temporal / weighting / integration / regression / ranking-impact / final qualification / decision synthesis
```

## Pre-decision checklist

Before proposing a production change to any event:

- Check this index for an existing frozen or provisional audit state.
- Read the dedicated `docs/<EVENT>_AUDIT.md` record when present.
- Read the dedicated decision-synthesis document when an event has one.
- Reuse frozen populations and existing audit outputs.
- Do not rerun an audit unless the code, semantics, scoring architecture, population contract, independent validation window, or counterfactual framework materially changed.
- Do not confuse runtime `Evidence.weight` with professional scoring-map weights.
- Treat historical outcome association as evidence for study, not automatic authorization for production penalties or bonuses.
- Preserve the project's real-market VSA principle: imperfect but meaningful VSA evidence is valid when the methodology is still respected.
