# Specification 001

# Stopping Volume

Version: 1.0

Status: Approved

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

Typical characteristics

- Exceptionally high volume
- Relatively wide spread
- Close well off the lows
- Usually appears after weakness

Professional money cannot buy quietly.

---

# Wyckoff Interpretation

Stopping Volume represents

Demand overcoming Supply.

Depending on subsequent price action, it may become

- Selling Climax
- Automatic Rally
- Secondary Test

Therefore

Stopping Volume alone is NOT confirmation.

It is evidence.

---

# Professional Interpretation

Professional demand has entered the market.

Supply may be reducing.

Further confirmation is required.

---

# Inputs

Version 1 uses only objective measurements.

Required metrics

- Volume Percentile
- Spread Percentile
- Close Ratio

No trend.

No background.

No Wyckoff phase.

---

# Detection Conditions

## Condition 1

Professional Activity

Volume Percentile

>= STOPPING_VOLUME_MIN_VOLUME_PERCENTILE

---

## Condition 2

Large Effort

Spread Percentile

>= STOPPING_VOLUME_MIN_SPREAD_PERCENTILE

---

## Condition 3

Buying Response

Close Ratio

>= STOPPING_VOLUME_MIN_CLOSE_RATIO

---

# Output

Produces

SmartMoneyEvidence

Code

STOPPING_VOLUME

Category

DEMAND

Direction

BULLISH

Strength

STRONG

---

# Confidence

Computed from

- Volume Percentile
- Spread Percentile
- Close Ratio

Mean of normalized values.

---

# Weight

STOPPING_VOLUME_WEIGHT

---

# False Positives

Do NOT detect

High Volume

+

Weak Close

↓

Likely Selling Climax

---

High Volume

+

Narrow Spread

↓

Likely Absorption

---

Average Volume

+

Wide Spread

↓

Normal Volatility

---

# Unit Tests

Positive

92 Volume

80 Spread

0.82 Close

↓

Detected

---

Negative

60 Volume

80 Spread

0.82 Close

↓

Not detected

---

Negative

95 Volume

50 Spread

0.82 Close

↓

Not detected

---

Negative

95 Volume

80 Spread

0.30 Close

↓

Not detected

---

Boundary

Exactly

Volume = Threshold

Spread = Threshold

Close = Threshold

↓

Detected

---

# Future Enhancements

Version 2

- Downtrend confirmation
- Weak background
- Previous selling pressure

Version 3

- Wyckoff phase
- Composite Operator activity
- Nearby Smart Money evidence
- Spring/Test interaction

---

End of Specification