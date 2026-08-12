# Primary VSA Event Matrix

This document is a production-coverage inventory for the VSA event layer on `main`.

It is a specification/diagnostic artifact only. It does not change detector logic, evidence weights, qualification rules, or scanner behavior.

## Production collection path

`EvidenceEngine.collect()` currently invokes:

- `collect_supply()`
- `collect_demand()`
- `collect_structural_progression()`

Inside `collect_supply()`, these detectors are currently called for every eligible bar:

- `BUYING_CLIMAX`
- `SUPPLY_COMING_IN`
- `HIDDEN_SUPPLY`
- `INCREASING_SUPPLY`
- `SUPPLY_DRYING_UP`
- `UPTHRUST`
- `NO_DEMAND`

Inside `collect_demand()`, `SHAKEOUT` and `NO_SUPPLY` are currently active. Selling Climax and Test remain disabled.

## Matrix

| EvidenceCode | Detector | Production path | Audit/research status | Role | Direction | Notes |
|---|---|---:|---:|---|---|---|
| `BUYING_CLIMAX` | `evidence/supply.py::_collect_buying_climax` | YES | YES | Primary weakness / supply | Bearish | Requires buying campaign, bullish bar, very-high volume, above-average spread; confirmations include wide spread, weak close, increasing volume. |
| `SUPPLY_COMING_IN` | `evidence/supply.py::_collect_supply_coming_in` | YES | YES | Primary weakness / supply | Bearish | Down bar with high volume, above-average spread, weak close, increasing volume. |
| `INCREASING_SUPPLY` | `evidence/supply.py::_collect_increasing_supply` | YES | YES | Primary weakness / supply | Bearish | Down bar + increasing volume + increasing spread. Used by current scanner continuation logic. |
| `HIDDEN_SUPPLY` | `evidence/supply.py::_collect_hidden_supply` | YES | YES | Supporting supply | Bearish | Up bar + high volume + lower close. |
| `SUPPLY_DRYING_UP` | `evidence/supply.py::_collect_supply_drying_up` | YES | YES | Supporting / exhaustion context | Bearish observation of drying supply | Down bar + low volume + narrow spread; should not automatically be treated as bearish pressure. |
| `UPTHRUST` | `evidence/supply.py::_collect_upthrust` | YES | YES | Primary trap / supply | Bearish | Buying campaign + bullish bar + very-high volume + above-average spread; confirmations include wide spread, weak close, lower close than previous. |
| `NO_DEMAND` | `evidence/supply.py::_collect_no_demand` | YES | YES | Primary weakness / demand absence | Bearish | Detected in supply collector despite belonging semantically to demand absence. Bullish environment + bullish bar + low volume + narrow spread. |
| `SHAKEOUT` | `evidence/demand.py::_collect_shakeout` | YES | YES | Primary reversal / demand | Bullish | Selling pressure + bearish bar + wide spread + very-high volume + strong close + lower low, then validated recovery/test. |
| `NO_SUPPLY` | `evidence/demand.py::_collect_no_supply` | YES | Audit-capable | Primary demand absence | Bullish | Detector exists and is now enabled in `collect_demand()`. |
| `STOPPING_VOLUME` | No active production detector identified | NO | Candidate / missing | Primary demand | Bullish | Enum exists; needs a deliberate strict-VSA detector decision before implementation. |
| `DEMAND_COMING_IN` | No active production detector identified | NO | Candidate / missing | Primary demand | Bullish | Enum exists; needs explicit detector specification. |
| `INCREASING_DEMAND` | No active production detector identified | NO | Candidate / missing | Primary demand | Bullish | Enum exists; needs explicit detector specification. |
| `HIDDEN_DEMAND` | No active production detector identified | NO | Candidate / missing | Supporting demand | Bullish | Enum exists; needs explicit detector specification. |
| `DEMAND_DRYING_UP` | No active production detector identified | NO | Candidate / missing | Supporting / exhaustion context | Bullish observation of drying demand | Must be distinguished from bearish absence-of-demand events. |
| `SELLING_CLIMAX` | `evidence/demand.py::_collect_selling_climax` | NO (commented out) | Audit-capable | Primary demand / reversal | Bullish | Detector exists but is disabled in `collect_demand()`. |
| `TEST` | `evidence/demand.py::_collect_test` | NO (commented out) | Audit-capable | Primary confirmation | Bullish | Detector exists but is disabled in `collect_demand()`. Audit currently shows that a low-volume/narrow-spread test bar alone is too broad; context and subsequent response matter. |
| `SPRING` | No active production detector identified | NO | Candidate / missing | Primary trap / reversal | Bullish | Enum exists; needs explicit strict-VSA/Wyckoff definition. |
| `ABSORPTION` | No dedicated production detector confirmed | NO | Present in model/registry | Primary/supporting absorption | Neutral / directional by context | Atomic effort-result observation; must be given one canonical production detector before use. |
| `EFFORT_GT_RESULT` | `evidence/effort.py` | Engine invocation currently disabled | Present | Effort/result context | Neutral | Separate from primary supply/demand event detection. |
| `RESULT_GT_EFFORT` | `evidence/effort.py` | Engine invocation currently disabled | Present | Effort/result context | Neutral | Separate from primary supply/demand event detection. |
| `EFFORT_RESULT` | No dedicated active event detector confirmed | NO | Candidate | Effort/result context | Neutral | Needs one canonical representation if retained. |
| `SUPPLY_ABSORPTION` | Detector block is commented in `evidence/supply.py` | NO | Candidate | Supply absorption | Bullish/neutral depending rule | Must not be implemented until semantics are frozen. |
| `SUPPLY_HIGH_VOLUME` | Detector block is commented in `evidence/supply.py` | NO | Candidate | Supply descriptor | Bearish | Likely descriptive rather than a standalone primary signal. |
| `SUPPLY_WIDE_SPREAD` | Detector block is commented in `evidence/supply.py` | NO | Candidate | Supply descriptor | Bearish | Likely descriptive rather than a standalone primary signal. |
| `STRUCTURAL_PROGRESSION_IMPROVING` | `background/structural_progression.py` | YES | YES | Structural | Bullish | Structural context, not a raw VSA primary event. |
| `STRUCTURAL_PROGRESSION_WEAKENING` | `background/structural_progression.py` | YES | YES | Structural | Bearish | Structural context, not a raw VSA primary event. |

## Immediate conclusions

1. The production event layer is currently **supply-heavy**. Multiple bearish/supply detectors are active, while several canonical bullish/demand-side VSA events are implemented but disabled or not yet implemented.
2. `NO_DEMAND` is being collected from the supply collector. That is a semantic organization issue worth cleaning up later, but not by changing its detector behavior in this milestone.
3. `SUPPLY_DRYING_UP` is an important semantic case: it should remain an observation/context event and should not automatically imply stronger bearish pressure.
4. `ABSORPTION` is an atomic effort-result observation in the model/registry, but it currently lacks a single canonical production detector and should not be scored until semantics are frozen. 
5. `EFFORT_GT_RESULT`, `RESULT_GT_EFFORT`, trend, phase, and structural progression belong to separate analytical layers and should not be promoted into the primary VSA event set.
6. The next implementation milestone should be **bullish/demand-side detector coverage**, beginning with `SELLING_CLIMAX` and `TEST`, because their strict-VSA detector code already exists and can be audited before introducing entirely new formulas for missing events such as `SPRING` or `INCREASING_DEMAND`.

## TEST audit findings

The current audit population contains six detected TEST events: bars `149`, `152`, `248`, `338`, `346`, and `510`.

Early results indicate a meaningful separation between two real-market contexts:

- `149`, `152`, and `248` occur with recent structural weakness but without a confirmed downtrend.
- `338`, `346`, and `510` occur inside a confirmed healthy downtrend without the same structural-weakness signature and are followed by renewed `INCREASING_SUPPLY` in the audit window.

The audit also shows that perfect textbook confirmation is **not required for every useful real-market TEST**. For example, `152` has low volume, narrow spread, decreasing volume, and a higher low but not a strong close, while still being followed by meaningful improvement in price. Conversely, `338`, `346`, and `510` satisfy the detector's mandatory conditions yet fail to produce convincing bullish follow-through.

Current working interpretation:

> A production-quality TEST should be evaluated as a **contextual market event**, not as a textbook single-bar pattern. Low-effort/narrow-spread behavior is meaningful only in relation to the preceding selling campaign, structural condition, and subsequent response to supply.

This is an **audit hypothesis, not a frozen detector rule**. It must be validated on additional history before `_collect_test()` is changed or enabled.

## Real-market VSA rule

The project should not require textbook-perfect VSA scenarios in order to recognize a useful event. VSA characteristics may be incomplete, distributed across several bars, or expressed through confluence rather than a single ideal bar. Detector logic should therefore prioritize:

- contextual confluence,
- effort versus result,
- campaign background,
- structural consequence,
- subsequent response,
- and contradiction from opposing evidence.

A detector should reject an event when its broader context materially contradicts the intended VSA interpretation, but it should not reject a useful real-market event merely because one textbook characteristic is absent.

## Freeze rule

Until the event-by-event tests are complete, do not change numeric weights or scanner actionability rules. The purpose of this matrix is to make detector semantics and coverage explicit before campaign aggregation is promoted into production.
