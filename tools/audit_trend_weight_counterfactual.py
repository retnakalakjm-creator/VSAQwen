from pathlib import Path

import pandas as pd


# --------------------------------------------------
# Configuration
# --------------------------------------------------

INPUT_FILE = Path("historical_validation.csv")
OUTPUT_FILE = Path("trend_weight_counterfactual.csv")


# --------------------------------------------------
# Current production trend adjustments
# --------------------------------------------------

TREND_ADJUSTMENTS = {
    "UPTHRUST": {
        "HEALTHY": -0.20,
        "EXHAUSTED": 0.30,
    },
    "SUPPLY_COMING_IN": {
        "HEALTHY": 0.00,
        "EXHAUSTED": 0.30,
    },
    "SHAKEOUT": {
        "HEALTHY": 0.00,
        "EXHAUSTED": 0.00,
    },
}


# --------------------------------------------------
# Load
# --------------------------------------------------

if not INPUT_FILE.exists():
    raise FileNotFoundError(
        f"File not found: {INPUT_FILE}"
    )

df = pd.read_csv(INPUT_FILE)


required = {
    "event",
    "trend_state",
    "weight",
}

missing = required - set(df.columns)

if missing:
    raise ValueError(
        f"Missing required columns: {sorted(missing)}"
    )


# --------------------------------------------------
# Normalize text
# --------------------------------------------------

df["event"] = (
    df["event"]
    .astype(str)
    .str.strip()
    .str.upper()
)

df["trend_state"] = (
    df["trend_state"]
    .astype(str)
    .str.strip()
    .str.upper()
)


# --------------------------------------------------
# Trend adjustment
# --------------------------------------------------

def get_trend_adjustment(row: pd.Series) -> float:
    event = row["event"]
    state = row["trend_state"]

    return TREND_ADJUSTMENTS.get(
        event,
        {},
    ).get(
        state,
        0.00,
    )


df["trend_adjustment"] = df.apply(
    get_trend_adjustment,
    axis=1,
)


# --------------------------------------------------
# Counterfactual
# --------------------------------------------------
#
# actual_weight =
#     base + environment + trend + structure + ...
#
# Therefore:
#
# weight_without_trend =
#     actual_weight - trend_adjustment
#
# We are deliberately NOT recalculating the
# entire WeightCalculator here.
# --------------------------------------------------

df["weight_without_trend"] = (
    df["weight"]
    - df["trend_adjustment"]
)


# --------------------------------------------------
# Useful diagnostic
# --------------------------------------------------

df["trend_effect_pct"] = (
    df["trend_adjustment"]
    / df["weight_without_trend"].replace(0, pd.NA)
    * 100.0
)


# --------------------------------------------------
# Select output columns
# --------------------------------------------------

front = [
    "event",
    "trend_state",
    "symbol",
    "week",
    "weight",
    "trend_adjustment",
    "weight_without_trend",
]

out_columns = [
    col
    for col in front
    if col in df.columns
]

remaining = [
    col
    for col in df.columns
    if col not in out_columns
]

result = df[
    out_columns + remaining
]


# --------------------------------------------------
# Save
# --------------------------------------------------

result.to_csv(
    OUTPUT_FILE,
    index=False,
)


# --------------------------------------------------
# Detail
# --------------------------------------------------

print()
print("=" * 72)
print("TREND WEIGHT COUNTERFACTUAL AUDIT")
print("=" * 72)

print()
print(f"Cases: {len(result)}")
print(f"Output: {OUTPUT_FILE}")

print()
print(
    result[
        [
            "event",
            "trend_state",
            "symbol",
            "weight",
            "trend_adjustment",
            "weight_without_trend",
        ]
    ].to_string(index=False)
)


# --------------------------------------------------
# Summary
# --------------------------------------------------

summary = (
    result
    .groupby(
        ["event", "trend_state"],
        dropna=False,
    )
    .agg(
        n=("weight", "count"),
        avg_trend_adjustment=(
            "trend_adjustment",
            "mean",
        ),
        avg_weight=(
            "weight",
            "mean",
        ),
        avg_weight_without_trend=(
            "weight_without_trend",
            "mean",
        ),
        min_weight=(
            "weight",
            "min",
        ),
        max_weight=(
            "weight",
            "max",
        ),
    )
    .reset_index()
)


print()
print("=" * 72)
print("SUMMARY")
print("=" * 72)
print()

print(
    summary.to_string(
        index=False,
        float_format=lambda x: f"{x:.3f}",
    )
)