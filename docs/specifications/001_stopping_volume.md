# Specification 001

# Stopping Volume

Version: 2.0

Status: Production

---

# Purpose

Detect the first appearance of professional demand capable of
halting or absorbing aggressive selling pressure.

Stopping Volume is an observation.

It is NOT a buy signal.

---

# Classical Definition (Tom Williams)

Stopping Volume occurs when professional money absorbs
significant selling.

Typical characteristics:

- significant selling campaign / prior weakness
- bearish current bar
- high volume
- above-average spread
- close off the low

The key VSA interpretation is effort versus result:
heavy selling effort is present, but the close shows that
selling did not fully control the result.

---

# Wyckoff Interpretation

Stopping Volume represents demand entering into a market
under selling pressure.

Depending on subsequent price action, it may contribute to
recognition of a Selling Climax, Automatic Rally, Secondary Test,
or later accumulation evidence.

Stopping Volume alone is NOT confirmation.

It is evidence.

---

# Production Validation

The production definition was validated using chronological
point-in-time replay across eight symbols.

Validated population:

- 59 events
- 39 positive 8-bar outcomes
- 14 negative 8-bar outcomes
- 6 flat outcomes
- 53 decisive outcomes
- 73.58% positive decisive rate

Leave-one-symbol-out positive decisive rates remained between
68.29% and 80.43%, so the result was not dependent on one symbol.

One symbol, RELIANCE.NS, was materially weaker than the rest and
is intentionally retained in the validation universe rather than
filtered out.

---

# Inputs

Stopping Volume now uses both market context and objective bar
measurements.

Required context:

- Selling Campaign

Required bar conditions:

- Bearish Bar
- High Volume
- Above-Average Spread
- Close Off Low

These five conditions are mandatory.

---

# Detection Conditions

## Condition 1 — Selling Campaign

`has_selling_campaign(ctx)` must be true.

The campaign is based on recent weakness using the existing
campaign engine. It can be established through a combination of:

- confirmed downtrend
- repeated down bars
- repeated lower closes
- repeated weak closes
- structural weakness

The campaign score remains governed by the existing campaign
configuration. No new campaign threshold was introduced for
Stopping Volume.

---

## Condition 2 — Bearish Bar

The current bar must be bearish/down.

---

## Condition 3 — High Volume

The current bar must have at least the `HIGH` VSA volume class.

---

## Condition 4 — Above-Average Spread

The current bar spread must be at least `ABOVE_AVERAGE`.

---

## Condition 5 — Close Off Low

The current bar must NOT have a weak/lower close.

This intentionally accepts imperfect real-market closes rather than
requiring a textbook near-high close.

---

# Confirmations

The following observations are recorded as confirmations and are
NOT mandatory detection gates:

- Very High Volume
- Wide Spread
- Increasing Volume
- Higher Low

The detector therefore preserves meaningful imperfect real-market
Stopping Volume observations while retaining stronger confirmations
for downstream quality/scoring analysis.

---

# Output

Produces:

`EvidenceCode.STOPPING_VOLUME`

Category:

`DEMAND`

Direction:

`BULLISH`

The evidence registry retains the validated baseline weight:

`STOPPING_VOLUME = 1.00`

No production weight optimization was justified by the validation
work performed so far.

---

# Confidence

Confidence remains derived from the existing evidence-construction
pipeline rather than introducing a new outcome-fitted formula.

The detection gate is semantic VSA evidence; confidence and weight are
separate downstream dimensions.

---

# False Positives

Do NOT classify a bar as Stopping Volume solely because it has:

- high/exceptional volume
- wide spread
- strong close

without the prior selling-campaign context and bearish current-bar
requirement.

High-volume bullish expansion should not be mislabeled as Stopping
Volume.

---

# Unit Tests

The detector must verify:

- all five mandatory requirements pass -> evidence emitted
- each mandatory requirement fails independently -> no evidence
- confirmation failures do NOT suppress a valid detection
- Stopping Volume is included by `collect_demand()` in the production
  EvidenceEngine path

---

# Audit Boundary

The historical replay used for validation is point-in-time:
validation decisions at bar `t` use only information available through
bar `t`.

Forward 1/2/4/8-bar outcomes are used only for post-event evaluation
and never for detection.

---

# Future Enhancements

Potential later work, only after separate validation:

- stronger absorption quality scoring
- interaction with Spring and Test
- regime-specific behavior
- conditional weight calibration

These are not part of the current production detection rule.

---

End of Specification
