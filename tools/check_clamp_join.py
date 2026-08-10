import pandas as pd

weights = pd.read_csv("trend_weight_counterfactual.csv")
outcomes = pd.read_csv("trend_outcome_audit.csv")

print("\nWEIGHT FILE")
print(weights[[
    "event",
    "trend_state",
    "symbol",
    "week",
]].head(10).to_string(index=False))

print("\nOUTCOME FILE")
print(outcomes[[
    "event",
    "trend_state",
    "symbol",
    "week",
]].head(10).to_string(index=False))

print("\nDTYPES")
print("\nweights:")
print(weights[[
    "event",
    "trend_state",
    "symbol",
    "week",
]].dtypes)

print("\noutcomes:")
print(outcomes[[
    "event",
    "trend_state",
    "symbol",
    "week",
]].dtypes)

print("\nWEEK EXAMPLES")
print(
    "weights:",
    weights["week"].dropna().head(10).tolist()
)

print(
    "outcomes:",
    outcomes["week"].dropna().head(10).tolist()
)