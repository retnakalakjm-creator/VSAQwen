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
| `TEST` | `evidence/demand.py::_collect_test` | NO (commented out) | Audit-complete / frozen semantics | Primary confirmation | Bullish | Detector remains disabled. Full-history audit shows TEST must be treated as a contextual low-effort probe after recent selling pressure; no single textbook precursor, structural location, score, or confirmation checklist reliably separates successes from failures. |
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

The full-history audit currently contains eight detected TEST events: bars `149`, `152`, `248`, `338`, `346`, `510`, `942`, and `1084`.

The audits establish that:

- textbook-perfect TEST confirmations are not required for every useful real-market instance;
- a simple point-in-time support score does not reliably separate successful and failed TESTs;
- structural location near a prior low is neither necessary nor sufficient;
- a simple pre-TEST change-of-character count is not a reliable standalone discriminator;
- a rigid `high effort -> weak result -> TEST` precursor sequence is also not required;
- immediate area failure and renewed supply are materially important validation outcomes, but they occur after the TEST and therefore cannot be used as historical detector inputs without future leakage.

Examples:

- `248` is the strongest positive example: all three contextual confirmations pass and the TEST area holds through the four-bar response window.
- `942` is a critical counterexample: it has structural weakness, no confirmed downtrend, higher low, and decreasing volume, yet it fails the area immediately and renewed supply appears.
- `346`, `942`, and `1084` show descriptive loss of selling effectiveness before TEST, but all three fail afterward. This prevents us from making “selling effectiveness is visibly losing” a mandatory TEST precursor.

### Frozen TEST semantic interpretation

> **TEST is a low-effort probe after meaningful recent selling pressure. It establishes an observation, not proof of demand control. Its meaning comes from the combined context and later validation rather than from a textbook-perfect single-bar pattern.**

For implementation purposes, the layers are:

1. **Event evidence:** down bar + low volume + narrow spread.
2. **Campaign context:** meaningful recent selling pressure and broader structural environment.
3. **Supporting evidence:** decreasing volume, higher low, acceptable/strong close, supply drying, or related structural context when present.
4. **Contradictory context:** persistent supply, materially bearish structure, or other evidence inconsistent with a bullish Test interpretation should weaken the event rather than being ignored.
5. **Validation:** post-TEST area holding and subsequent demand/supply response belong to downstream persistence/qualification, not to the historical detector itself.

No single supporting factor is promoted to a mandatory textbook gate on the basis of this sample.

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

The TEST semantics are now frozen for this audit milestone. Do not add new TEST checklist conditions, numeric weights, or scanner actionability rules unless new evidence materially changes the interpretation. The next production step is to map this frozen semantic model onto the existing detector with the smallest possible change, then audit the resulting production-path behavior before enabling actionability.
