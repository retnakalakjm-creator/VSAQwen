from pathlib import Path

import pandas as pd


INPUT_FILE = Path("trend_weight_counterfactual.csv")

LOWER_CLAMP = 0.50
UPPER_CLAMP = 2.00


def clamp(value: float) -> float:
    return max(
        LOWER_CLAMP,
        min(value, UPPER_CLAMP),
    )


df = pd.read_csv(INPUT_FILE)


required = {
    "event",
    "trend_state",
    "weight",
    "trend_adjustment",
    "weight_without_trend",
    "base_weight",
    "environment_adjustment",
    "structural_adjustment",
}

missing = required - set(df.columns)

if missing:
    raise ValueError(
        f"Missing columns: {sorted(missing)}"
    )


# --------------------------------------------------
# IMPORTANT
# --------------------------------------------------
#
# weight_without_trend is already supplied by
# the audit CSV.
#
# Therefore:
#
# raw weight
#     = weight_without_trend + trend_adjustment
#
# We do NOT attempt to reconstruct climactic
# adjustment separately.
# --------------------------------------------------

df["raw_weight"] = (
    df["weight_without_trend"]
    + df["trend_adjustment"]
)


# --------------------------------------------------
# Raw score without trend
# --------------------------------------------------

df["raw_without_trend"] = (
    df["weight_without_trend"]
)


# --------------------------------------------------
# Apply production clamp
# --------------------------------------------------

df["reconstructed_weight"] = (
    df["raw_weight"].apply(clamp)
)

df["counterfactual_weight"] = (
    df["raw_without_trend"].apply(clamp)
)


# --------------------------------------------------
# Verify against recorded weight
# --------------------------------------------------

df["reconstruction_error"] = (
    df["reconstructed_weight"]
    - df["weight"]
).abs()


bad = df["reconstruction_error"] > 1e-9

if bad.any():

    print()
    print("WARNING: reconstructed weight differs")
    print("from recorded production weight.")
    print()

    print(
        df.loc[
            bad,
            [
                "event",
                "trend_state",
                "symbol",
                "weight",
                "weight_without_trend",
                "trend_adjustment",
                "raw_weight",
                "reconstructed_weight",
            ],
        ]
        .head(20)
        .to_string(index=False)
    )


# --------------------------------------------------
# Clamp state
# --------------------------------------------------

df["clamp_state"] = "NONE"

df.loc[
    df["raw_weight"] <= LOWER_CLAMP,
    "clamp_state",
] = "LOWER"

df.loc[
    df["raw_weight"] >= UPPER_CLAMP,
    "clamp_state",
] = "UPPER"


# --------------------------------------------------
# Actual trend effect after clamp
# --------------------------------------------------

df["trend_effect"] = (
    df["reconstructed_weight"]
    - df["counterfactual_weight"]
)

df["trend_effective"] = (
    df["trend_effect"].abs() > 1e-9
)


# --------------------------------------------------
# Summary
# --------------------------------------------------

summary = (
    df.groupby(
        ["event", "trend_state"],
        dropna=False,
    )
    .agg(
        cases=("weight", "count"),

        avg_trend_adjustment=(
            "trend_adjustment",
            "mean",
        ),

        avg_raw_weight=(
            "raw_weight",
            "mean",
        ),

        avg_final_weight=(
            "reconstructed_weight",
            "mean",
        ),

        avg_counterfactual_weight=(
            "counterfactual_weight",
            "mean",
        ),

        avg_actual_trend_effect=(
            "trend_effect",
            "mean",
        ),

        effective_cases=(
            "trend_effective",
            "sum",
        ),

        lower_clamped=(
            "clamp_state",
            lambda x: (x == "LOWER").sum(),
        ),

        upper_clamped=(
            "clamp_state",
            lambda x: (x == "UPPER").sum(),
        ),
    )
    .reset_index()
)


summary["effective_pct"] = (
    summary["effective_cases"]
    / summary["cases"]
    * 100.0
)

summary["lower_clamp_pct"] = (
    summary["lower_clamped"]
    / summary["cases"]
    * 100.0
)

summary["upper_clamp_pct"] = (
    summary["upper_clamped"]
    / summary["cases"]
    * 100.0
)


# --------------------------------------------------
# Output
# --------------------------------------------------

output = Path(
    "weight_clamp_audit_corrected.csv"
)

summary.to_csv(
    output,
    index=False,
)


print()
print("=" * 120)
print("CORRECTED PRE-CLAMP WEIGHT AUDIT")
print("=" * 120)
print()

columns = [
    "event",
    "trend_state",
    "cases",
    "avg_trend_adjustment",
    "avg_raw_weight",
    "avg_final_weight",
    "avg_counterfactual_weight",
    "avg_actual_trend_effect",
    "effective_cases",
    "effective_pct",
    "lower_clamped",
    "lower_clamp_pct",
    "upper_clamped",
    "upper_clamp_pct",
]

print(
    summary[columns].to_string(
        index=False,
        float_format=lambda x: f"{x:.3f}",
    )
)

print()
print(f"Output: {output}")