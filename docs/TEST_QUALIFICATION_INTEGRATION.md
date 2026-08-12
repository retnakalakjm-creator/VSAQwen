# TEST Qualification Integration

## Decision

`TEST` should remain a contextual VSA event and should **not** be inserted into `PatternQualificationEngine` as a qualifying event.

The qualification engine is explicitly designed to validate persistent chronological `STRUCTURAL_PROGRESSION_IMPROVING` / `STRUCTURAL_PROGRESSION_WEAKENING` events. It is not a generic VSA-event persistence engine.

## Why

The TEST audits established:

- TEST alone does not prove demand control.
- TEST + `SUPPLY_DRYING_UP` occurs in both successful and failed cases.
- Strong contradiction does not reliably separate outcomes.
- No tested numeric TEST weight produced useful outcome separation.
- Post-TEST area holding and subsequent response are meaningful validation, but are future information at detection time.

Therefore TEST should remain available in the evidence stream while downstream validation observes what happens after the probe.

## Current role

`TEST`:

- is collected in the production evidence path;
- remains a bullish/contextual observation;
- contributes no standalone professional demand score;
- does not qualify a pattern by itself;
- does not create persistence by itself;
- may participate in future validation/diagnostic reporting alongside structural progression and subsequent supply/demand response.

## Real-market VSA rule

Do not force a textbook TEST sequence into the qualification layer. A real-market TEST may be incomplete or only meaningful in confluence with other evidence. Its eventual success is established by the market response, not by the detector claiming success at the event bar.

## Freeze

No production qualification change is justified by the current TEST sample. Future TEST qualification work should begin only after a larger validation set demonstrates a stable relationship between TEST occurrences and subsequent response.
